""" Sixth version, make the code easier and more modifiable """
# Define the main programme

from funcs import store_namespace
from funcs import load_namespace
from funcs import emulate_jmod
import os
import datetime
import time
import pandas as pd
#from multiprocessing import Pool
from mpcpy import units
from mpcpy import variables
from mpcpy import models_mod as models

from Simulator_HP_mod3 import SimHandler

if __name__ == "__main__":  
    
    # Naming conventions for the simulation
    community = 'ResidentialCommunityUK_rad_2elements'
    sim_id = 'MinEne'
    model_id = 'R2CW_HP'
    bldg_list = load_namespace(os.path.join('path_to_models', 'teaser_bldgs_residentialUK_10bldgs_fallback'))
    folder = 'results'
    bldg_index_start = 0
    bldg_index_end = 10
    
    # Overall options
    date = '1/7/2017 '
    start = date + '16:30:00'
    end = date + '19:00:00'
    meas_sampl = '300'
    horizon = 2*3600/float(meas_sampl) #time horizon for optimization in multiples of the sample
    mon = 'jan'
    
    DRstart = datetime.datetime.strptime(date + '17:30:00', '%m/%d/%Y %H:%M:%S') # hour to start DR - ramp down 30 mins before
    DRend = datetime.datetime.strptime(date + '18:30:00', '%m/%d/%Y %H:%M:%S') # hour to end DR - ramp 30 mins later
    DR_call_start = datetime.datetime.strptime(date + '17:00:00', '%m/%d/%Y %H:%M:%S') # Round of loop to implement the call
    DR_ramp_start = datetime.datetime.strptime(date + '17:30:00', '%m/%d/%Y %H:%M:%S')
    DR_ramp_end = datetime.datetime.strptime(date + '18:30:00', '%m/%d/%Y %H:%M:%S') # Round of loop to stop implementing the call
    flex_cost = 150 # Cost for flexibility
    
    compr_capacity=float(3000)
    
    ramp_modifier = float(2000/compr_capacity) # to further modify the load profile
    max_modifier = float(2000/compr_capacity)
    
    dyn_price = 1
    stat_cost = 50
    #set_change = 1
    
    sim_range = pd.date_range(start, end, freq = meas_sampl+'S')
    opt_start_str = start
    opt_end = datetime.datetime.strptime(end, '%m/%d/%Y %H:%M:%S') + datetime.timedelta(seconds = horizon*int(meas_sampl))
    opt_end_str = opt_end.strftime('%m/%d/%Y %H:%M:%S')
    
    init_start = sim_range[0] - datetime.timedelta(seconds = 0.5*3600)
    init_start_str = init_start.strftime('%m/%d/%Y %H:%M:%S')
    print(init_start_str)
    
    

    # Instantiate Simulator for aggregated optimisation
    SimAggr = SimHandler(sim_start = start,
                sim_end = end,
                meas_sampl = meas_sampl
                )
                
    SimAggr.moinfo_mpc = (os.path.join(SimAggr.simu_path, 'AggrMPC_ResUK_10bldgs_heatpump_rad_fallback.mo'),
                'AggrMPC_ResUK_10bldgs_heatpump_rad_fallback.Residential',
                {}
                )
        
    SimAggr.building = 'AggrMPC_ResUK_10bldgs_heatpump_rad_fallback'
    SimAggr.target_variable = 'TotalHeatPower'

    # Not really used in this case ...
    SimAggr.fmupath_emu = os.path.join(SimAggr.simu_path, 'fmus', community, 'AggrMPC_ResUK_10bldgs_heatpump_rad_fallback_Residential.fmu')

    SimAggr.fmupath_mpc = os.path.join(SimAggr.simu_path, 'fmus', community, 'AggrMPC_ResUK_10bldgs_heatpump_rad_fallback_Residential.fmu')

    SimAggr.moinfo_emu = (os.path.join(SimAggr.simu_path, 'AggrMPC_ResUK_10bldgs_heatpump_rad_fallback.mo'),
                'AggrMPC_ResUK_10bldgs_heatpump_rad_fallback.Residential',
                {}
                )



    # Initialise aggregated model
    # Control
    bldg_control = load_namespace(os.path.join(SimAggr.simu_path, 'ibpsa_paper', '10bldgs_decentr_nodyn_jan', 'control_SemiDetached_2_R2CW_HP'))
    # Constraints
    bldg_constraints = load_namespace(os.path.join(SimAggr.simu_path, 'ibpsa_paper', '10bldgs_decentr_nodyn_jan', 'constraints_SemiDetached_2_R2CW_HP'))

    # Optimisation constraints variable map
    SimAggr.optcon_varmap = {}
    SimAggr.contr_varmap = {}
    SimAggr.addobj_varmap = {}
    SimAggr.slack_var = []
    
    for bldg in bldg_list:
        model_name = bldg+'_'+model_id
        for key in bldg_control.data:
            SimAggr.contr_varmap[key+'_'+bldg] = (key+'_'+bldg, bldg_control.data[key].get_display_unit())
        
        for key in bldg_constraints.data:
            for key1 in bldg_constraints.data[key]:
                if key1 != 'Slack_GTE' and key1 != 'Slack_LTE':
                    SimAggr.optcon_varmap[model_name+'_'+key1] = (model_name+'.'+key, key1, bldg_constraints.data[key][key1].get_display_unit())
                else:
                    SimAggr.optcon_varmap[model_name+'_'+key1] = (model_name + '_TAir' + '_Slack', key1[-3:], units.degC)
                    
        
        SimAggr.slack_var.append(model_name +'_TAir'+ '_Slack')
        SimAggr.addobj_varmap[model_name + '_TAir' + '_Slack'] = (model_name + '_TAir' + '_Slack', units.unit1)
    
    #exit()

    index = pd.date_range(init_start, opt_end_str, freq = meas_sampl+'S')

    SimAggr.constraint_csv = os.path.join(SimAggr.simu_path,'csvs','Constraints_AggrRes.csv')
    SimAggr.control_file = os.path.join(SimAggr.simu_path,'csvs','ControlSignal_AggrRes.csv')
    SimAggr.price_file = os.path.join(SimAggr.simu_path,'csvs','PriceSignal.csv')
    SimAggr.param_file = os.path.join(SimAggr.simu_path,'csvs','Parameters.csv')

    # Initialise exogenous data sources
    SimAggr.update_weather(init_start_str,opt_end_str)
    SimAggr.get_DRinfo(init_start_str,opt_end_str)
    
    SimAggr.get_control()
    SimAggr.get_params()
    
    SimAggr.get_other_input(init_start_str,opt_end_str)
    SimAggr.get_constraints(init_start_str,opt_end_str,upd_control = 1)
    
    # Empty old data
    SimAggr.parameters.data = {}
    SimAggr.control.data = {}
    SimAggr.constraints.data = {}
    SimAggr.meas_varmap_mpc = {}
    SimAggr.meas_vars_mpc = {}
    SimAggr.other_input.data = {}
    
    index = pd.date_range(init_start_str, opt_end_str, freq = meas_sampl+'S', tz=SimAggr.weather.tz_name)
    for bldg in bldg_list:
        #Parameters from system id
        bldg_params = load_namespace(os.path.join(SimAggr.simu_path, 'sysid', 'sysid_HPrad_2element_'+mon+'_600S','est_params_'+bldg+'_'+model_id))
        bldg_other_input = load_namespace(os.path.join(SimAggr.simu_path, 'ibpsa_paper', 'decentr_enemin_'+mon, 'other_input_'+bldg+'_'+model_id))
        bldg_constraints = load_namespace(os.path.join(SimAggr.simu_path, 'ibpsa_paper', 'decentr_enemin_'+mon, 'constraints_'+bldg+'_'+model_id))
        
        model_name = bldg+'_'+model_id
        
        pheat_min = pd.Series(0,index=index)
        pheat_max = pd.Series(1,index=index)
        bldg_constraints.data['HPPower']= {'GTE': variables.Timeseries('HPPower_GTE', pheat_min, units.W, tz_name=SimAggr.weather.tz_name), 
                    'LTE': variables.Timeseries('HPPower_LTE', pheat_max, units.W,tz_name=SimAggr.weather.tz_name)}
        
        #print(SimAggr.start_temp)
        for key in bldg_params:
            SimAggr.parameters.data[model_name+'.'+key] = {'Free': variables.Static('FreeOrNot', bldg_params[key]['Free'].data, units.boolean), 
                'Minimum': variables.Static('Min', bldg_params[key]['Minimum'].data, bldg_params[key]['Minimum'].get_display_unit()), 
                'Covariance': variables.Static('Covar', bldg_params[key]['Covariance'].data, bldg_params[key]['Covariance'].get_display_unit()), 
                'Value': variables.Static(model_name+'.'+key, bldg_params[key]['Value'].data, bldg_params[key]['Value'].get_display_unit()), 
                'Maximum': variables.Static('Max', bldg_params[key]['Maximum'].data, bldg_params[key]['Maximum'].get_display_unit())
                }
            
            SimAggr.update_params(model_name+'.heatCapacitor.T.start',SimAggr.start_temp,unit=units.degC)
            SimAggr.update_params(model_name+'.heatCapacitor1.T.start',SimAggr.start_temp, unit=units.degC)

        if dyn_price == 0:
            bldg_control = load_namespace(os.path.join(SimAggr.simu_path, 'ibpsa_paper', '10bldgs_decentr_'+'nodyn_'+mon, 'control_'+bldg+'_'+model_id))
        else:
            bldg_control = load_namespace(os.path.join(SimAggr.simu_path, 'ibpsa_paper', '10bldgs_decentr_'+'dyn_'+mon, 'control_'+bldg+'_'+model_id))
        
        
        for key in bldg_control.data:
            SimAggr.control.data[key+'_'+bldg] = variables.Timeseries(
                name = key+'_'+bldg,
                timeseries = bldg_control.data[key].display_data(), # use the same initial guess as with decentralised
                display_unit = bldg_control.data[key].get_display_unit(),
                tz_name = SimAggr.weather.tz_name
                )
        
        for key in bldg_constraints.data:
            if key == 'HPPower':
                SimAggr.constraints.data[key+'_'+bldg] = {}
            else:
                SimAggr.constraints.data[model_name+'.'+key] = {}
            for key1 in bldg_constraints.data[key]:
                if key == 'HPPower':
                    SimAggr.constraints.data[key+'_'+bldg][key1] = variables.Timeseries(
                        name = key+'_'+bldg+'_'+key1, 
                        timeseries = bldg_constraints.data[key][key1].display_data().loc[index], 
                        display_unit = bldg_constraints.data[key][key1].get_display_unit(), 
                        tz_name = SimAggr.weather.tz_name
                        )
                else:
                    if key1 == 'Slack_GTE' or key1 == 'Slack_LTE':
                        SimAggr.constraints.data[model_name+'.'+key][key1] = variables.Timeseries(
                            name = model_name+'_'+key+'_'+key1, 
                            timeseries = bldg_constraints.data[key][key1].display_data().loc[index], 
                            display_unit = bldg_constraints.data[key][key1].get_display_unit(), 
                            tz_name = SimAggr.weather.tz_name
                            )
                    else:
                        SimAggr.constraints.data[model_name+'.'+key][key1] = variables.Timeseries(
                        name = model_name+'_'+key+'_'+key1, 
                        timeseries = bldg_constraints.data[key][key1].display_data().loc[index], 
                        display_unit = bldg_constraints.data[key][key1].get_display_unit(), 
                        tz_name = SimAggr.weather.tz_name
                        )
        
        SimAggr.meas_varmap_mpc[model_name+'.'+'TAir'] = (model_name+'.'+'TAir', units.K)
        
        SimAggr.meas_vars_mpc[model_name+'.'+'TAir'] = {}
        SimAggr.meas_vars_mpc[model_name+'.'+'TAir']['Sample'] = variables.Static('sample_rate_TAir', int(meas_sampl), units.s)
    
        
    SimAggr.meas_varmap_emu = SimAggr.meas_varmap_mpc 
    SimAggr.meas_vars_emu = SimAggr.meas_vars_mpc
    
    
    index = pd.date_range(init_start_str, opt_end_str, freq = meas_sampl+'S')
    SimAggr.price = load_namespace(os.path.join('prices','sim_price_'+mon))

    if dyn_price == 0:
        index = pd.date_range(init_start_str, opt_end_str, freq = '1800S')
        price_signal = pd.Series(50,index=index)
        SimAggr.price.data = {"pi_e": variables.Timeseries('pi_e', price_signal,units.cents_kWh,tz_name=SimAggr.weather.tz_name)
        }
    
    store_namespace(os.path.join(folder, 'sim_price'), SimAggr.price)

    store_namespace(os.path.join(folder, 'params_'+SimAggr.building), SimAggr.parameters)
    store_namespace(os.path.join(folder, 'control_'+SimAggr.building), SimAggr.control)
    store_namespace(os.path.join(folder, 'constraints_'+SimAggr.building), SimAggr.constraints)
    
    SimAggr.init_models(use_ukf=0, use_fmu_emu=0, use_fmu_mpc=0) # Use for initialising models
    #SimAggr.init_refmodel(use_fmu=1)


    # Instantiate Simulator
    Emu_list = []
    i = 0
    for bldg in bldg_list[bldg_index_start:bldg_index_end]:
        i = i+1
        print('Instantiating emulation models, loop: ' + str(i))
        Sim = SimHandler(sim_start = start,
                    sim_end = end,
                    meas_sampl = meas_sampl
                    )
                    
        Sim.moinfo_mpc = (os.path.join(Sim.simu_path, 'Tutorial_'+model_id+'.mo'),
                    'Tutorial_'+model_id+'.'+model_id,
                    {}
                    )
        
            
        Sim.building = bldg+'_'+model_id
        
        Sim.fmupath_mpc = os.path.join(Sim.simu_path, 'fmus',community, 'Tutorial_'+model_id+'_'+model_id+'.fmu')
        
        Sim.fmupath_emu = os.path.join(Sim.simu_path, 'fmus', community, community+'_'+bldg+'_'+bldg+'_Models_'+bldg+'_House_mpc.fmu')
        
        Sim.fmupath_ref = os.path.join(Sim.simu_path, 'fmus', community, community+'_'+bldg+'_'+bldg+'_Models_'+bldg+'_House_PI.fmu')
        
        Sim.moinfo_emu = (os.path.join(Sim.mod_path, community, bldg,bldg+'_Models',bldg+'_House_mpc.mo'),  community+'.'+bldg+'.'+bldg+'_Models.'+bldg+'_House_mpc',
        {}
        )
        
        Sim.moinfo_emu_ref = (os.path.join(Sim.mod_path, community, bldg,bldg+'_Models',bldg+'_House_PI.mo'),   community+'.'+bldg+'.'+bldg+'_Models.'+bldg+'_House_PI',
        {}
        )
        
        # Initialise exogenous data sources
        if i == 1:
            Sim.weather = SimAggr.weather
            Sim.get_DRinfo(init_start_str,opt_end_str)
            Sim.flex_cost = SimAggr.flex_cost
            Sim.price = SimAggr.price
            Sim.rho = SimAggr.rho
            #Sim.addobj = SimAggr.addobj
        else:
            Sim.weather = Emu_list[i-2].weather
            Sim.flex_cost = Emu_list[i-2].flex_cost
            Sim.price = Emu_list[i-2].price
            Sim.rho = Emu_list[i-2].rho
            Sim.addobj = Emu_list[i-2].addobj
        
        #Sim.sim_start= '1/1/2017 00:00'
        Sim.get_control()
        #Sim.sim_start= start
        Sim.get_other_input(init_start_str,opt_end_str)
        Sim.get_constraints(init_start_str,opt_end_str,upd_control=1)

        Sim.param_file = os.path.join(Sim.simu_path,'csvs','Parameters_R2CW.csv')
        Sim.get_params()
        
        Sim.parameters.data = load_namespace(os.path.join(Sim.simu_path, 'sysid', 'sysid_HPrad_2element_'+mon+'_600S','est_params_'+Sim.building))
        Sim.other_input = load_namespace(os.path.join(Sim.simu_path, 'ibpsa_paper', 'decentr_enemin_'+mon, 'other_input_'+Sim.building))
        Sim.constraints = load_namespace(os.path.join(Sim.simu_path, 'ibpsa_paper', 'decentr_enemin_'+mon, 'constraints_'+Sim.building))
        
        # Add to list of simulations
        Emu_list.append(Sim)


        
    # Start the hourly loop
    i = 0
    emutemps = {}
    mpctemps = {}
    controlseq = {}
    power = {}
    opt_stats = {}
    refheat = []
    reftemps = []

    index = pd.date_range(start, opt_end_str, freq = meas_sampl+'S')
    flex_cost_signal = pd.Series(0,index=index)
    
    start_temps = []
    for Sim in Emu_list:
        while True:
            try:
                # Initialise models
                Sim.init_models(use_ukf=1, use_fmu_mpc=1, use_fmu_emu=1) # Use for initialising 
                emulate_jmod(Sim.emu, Sim.meas_vars_emu, Sim.meas_sampl, init_start_str, start)
                
                Sim.start_temp = Sim.emu.display_measurements('Measured').values[-1][-1]-273.15
                print(Sim.emu.display_measurements('Measured'))
                
                out_temp=Sim.weather.display_data()['weaTDryBul'].resample(meas_sampl+'S').ffill()[start]
                start_temp = Sim.start_temp
                print(out_temp)
                print(Sim.start_temp)
                
                Sim.mpc.measurements = {}
                Sim.mpc.measurements['TAir'] = Sim.emu.measurements['TAir']
                
                SimAggr.update_params(Sim.building+'.heatCapacitor.T.start',Sim.start_temp+273.15, units.K)
                SimAggr.update_params(Sim.building+'.heatCapacitor1.T.start',(7*Sim.start_temp+out_temp)/8+273.15, units.K)
                
                Sim.update_params('C1start', start_temp+273.15, units.K)
                Sim.update_params('C2start', (7*start_temp+out_temp)/8+273.15, units.K)
        
                break
            except:
                print('%%%%%%%%%%%%%%%%%% Failed, trying again! %%%%%%%%%%%%%%%%%%%%%%')
                continue
        
            

    print(sim_range)    
    for simtime in sim_range:
        i = i + 1
        print('%%%%%%%%% IN LOOP: ' + str(i) + ' %%%%%%%%%%%%%%%%%') 
        if i == 1:
            simtime_str = 'continue'
        else:
            simtime_str = 'continue'
        opt_start_str = simtime.strftime('%m/%d/%Y %H:%M:%S')
        opt_end = simtime + datetime.timedelta(seconds = horizon*int(SimAggr.meas_sampl))
        emu_end = simtime + datetime.timedelta(seconds = int(SimAggr.meas_sampl))
        opt_end_str = opt_end.strftime('%m/%d/%Y %H:%M:%S')
        emu_end_str = emu_end.strftime('%m/%d/%Y %H:%M:%S')

        simtime_naive = simtime.replace(tzinfo=None)        
        
        print('---- Simulation time: ' + str(simtime) + ' -------')
        print('---- Next time step: ' + str(emu_end) + ' -------')
        print('---- Optimisation horizon end: ' + str(opt_end) + ' -------')

        
        emutemps = {}
        mpctemps = {}
        controlseq = {}
        power = {}
        opt_stats = {}
        
        while True:
            try:
                # Optimise for next time step
                print("%%%%%% --- Optimising --- %%%%%%")
                SimAggr.opt_start = opt_start_str
                SimAggr.opt_end = opt_end_str
                
                if simtime.hour == DR_call_start.hour and simtime.minute == DR_call_start.minute:
                    print('%%%%%%%%%%%%%%% DR event called - flexibility profile defined %%%%%%%%%%%%%%%%%%%%%')
                    flex_cost_signal = pd.Series(0,index=index)
                    
                    j = 0
                    for bldg in bldg_list:
                        if j == 0:
                            load_profiles = pd.Series(SimAggr.opt_controlseq['HPPower_' + bldg].display_data().values, index = SimAggr.opt_controlseq['HPPower_' + bldg].display_data().index)
                        else:
                            load_profile = pd.Series(SimAggr.opt_controlseq['HPPower_' + bldg].display_data().values, index = SimAggr.opt_controlseq['HPPower_' + bldg].display_data().index)
                            load_profiles = pd.concat([load_profiles, load_profile], axis=1)
                        j = j+1
                    
                    load_profile_aggr  = load_profiles.sum(axis=1)
                    
                    #Shape the profile if required
                    for t in load_profile_aggr.index:
                        t = t.replace(tzinfo = None)
                        if t >= DRstart and t < DRend:
                            print(load_profile_aggr[t])
                            load_profile_aggr[t] = load_profile_aggr[t]-max_modifier
                            print(load_profile_aggr[t])
                            flex_cost_signal[t] = flex_cost 
                        if load_profile_aggr[t] < 0:
                            load_profile_aggr[t] = 0
                    
                    SimAggr.flex_cost.data = {"flex_cost": variables.Timeseries('flex_cost', flex_cost_signal, units.cents_kWh,tz_name=Sim.weather.tz_name)}
                    
                    SimAggr.ref_profile.data['ref_profile'] = variables.Timeseries(
                                    'ref_profile', 
                                    load_profile_aggr, 
                                    SimAggr.opt_controlseq['HPPower_'+bldg_list[0]].get_display_unit(), 
                                    tz_name = Sim.weather.tz_name
                                    )
                    
                    SimAggr.flex_cost.data = {"flex_cost": variables.Timeseries('flex_cost', flex_cost_signal,units.cents_kWh,tz_name=Sim.weather.tz_name)
                    }
                    
                    store_namespace('ref_profile_'+SimAggr.building, SimAggr.ref_profile)
                    store_namespace('flex_cost_'+SimAggr.building, SimAggr.flex_cost)
                
                if simtime_naive >= DR_ramp_start and simtime_naive <= DR_ramp_end:
                    print('%%%%%%%%%%%%%%% Load-tracking %%%%%%%%%%%%%%%%%%%%%')
                else:
                    print('%%%%%%%%%%%%%%% No load_tracking %%%%%%%%%%%%%%%%%%%%%')
                
                # ### Optimise ### 
                SimAggr.opt_control_minDRCost()
                
                mpctemps = SimAggr.mpc.display_measurements('Simulated')
                opt_stats = SimAggr.opt_problem.get_optimization_statistics()
                break
            except:
                print('%%%%%%%%%%%%%%%%%% Failed, trying again! %%%%%%%%%%%%%%%%%%%%%%')
                continue
            
        for Emu in Emu_list:
            while True:
                try:
                    controlseq[Emu.building] = SimAggr.opt_controlseq['HPPower_'+Emu.building[:-(len(model_id)+1)]].display_data()
                    
                    Emu.opt_controlseq = {'HPPower': variables.Timeseries(
                                        name = 'HPPower',   
                                        timeseries = SimAggr.opt_controlseq['HPPower_'+Emu.building[:-(len(model_id)+1)]].display_data(),
                                        display_unit = SimAggr.opt_controlseq['HPPower_'+Emu.building[:-(len(model_id)+1)]].get_display_unit(), 
                                        tz_name = SimAggr.weather.tz_name
                                        )}
                    
                    print("Emulating response")
                    Emu.emulate_opt(simtime_str,emu_end_str)
                    time.sleep(2)
                    
                    # Collect measurements
                    print(Emu.emu.display_measurements('Measured'))
                    emutemps[Emu.building] = Emu.emu.display_measurements('Measured').values[1][-1]-273.15
                    power[Emu.building] = Emu.emu.display_measurements('Measured').values[1][0]
                    
                    Emu.mpc.measurements = {}
                    Emu.mpc.measurements['TAir'] = Emu.emu.measurements['TAir']
                    
                    out_temp=Emu.weather.display_data()['weaTDryBul'].resample(meas_sampl+'S').ffill()[opt_start_str]
                    start_temp = Emu.emu.display_measurements('Measured').values[1][-1]-273.15
                    
                    Emu.update_params('C1start', start_temp+273.15, units.K)
                    Emu.update_params('C2start', (7*start_temp+out_temp)/8+273.15, units.K)
                    break
                except:
                    print('%%%%%%%%%%%%%%%%%% Failed, trying again! %%%%%%%%%%%%%%%%%%%%%%')
                    continue
                    
                    
            while True:
                try:
                    
                    if (simtime.minute % 20 == 0) and (simtime.second == 0):
                        print('Time to Kalman Filter!!')
                        Emu.mpc = models.Modelica(models.UKF,
                                        models.RMSE,
                                        Emu.mpc.measurements,
                                        moinfo = Emu.moinfo_mpc,
                                        parameter_data = Emu.parameters.data,
                                        weather_data = Emu.weather.data,
                                        control_data = Emu.control.data,
                                        other_inputs = Emu.other_input.data,
                                        tz_name = Emu.weather.tz_name,
                                        version = '1.0'
                                        )
                        
                        Emu.id_start = opt_start_str
                        Emu.id_end = emu_end_str
                        
                        Emu.sys_id()
                        Emu.parameters.data = Emu.mpc.parameter_data
                        
                        kalman_flag = 1
                    else:
                        kalman_flag = 0
                    
                    if kalman_flag == 1:
                        #Parameters from system id
                        bldg_params = load_namespace(os.path.join(SimAggr.simu_path, 'ibpsa_paper', 'est_params_'+Emu.building))
                        
                        model_name = Emu.building
                
                        #print(SimAggr.start_temp)
                        for key in bldg_params:
                            
                            SimAggr.parameters.data[model_name+'.'+key] = {'Free': variables.Static('FreeOrNot', bldg_params[key]['Free'].data, units.boolean), 
                                'Minimum': variables.Static('Min', bldg_params[key]['Minimum'].data, bldg_params[key]['Minimum'].get_display_unit()), 
                                'Covariance': variables.Static('Covar', bldg_params[key]['Covariance'].data, bldg_params[key]['Covariance'].get_display_unit()), 
                                'Value': variables.Static(model_name+'.'+key, bldg_params[key]['Value'].data, bldg_params[key]['Value'].get_display_unit()), 
                                'Maximum': variables.Static('Max', bldg_params[key]['Maximum'].data, bldg_params[key]['Maximum'].get_display_unit())
                                }
                            
                    SimAggr.update_params(Emu.building+'.heatCapacitor.T.start', start_temp+273.15, units.K)
                    SimAggr.update_params(Emu.building+'.heatCapacitor1.T.start', (7*start_temp+out_temp)/8+273.15, units.K)
                    
                    break
                except:
                    print('%%%%%%%%%%%%%%%%%% Failed, trying again! %%%%%%%%%%%%%%%%%%%%%%')
                    continue

        while True:
            try:
                store_namespace(os.path.join(folder,'opt_stats_'+SimAggr.building+'_'+sim_id+'_'+opt_start_str.replace('/','-').replace(':','-').replace(' ','-')), opt_stats)
                store_namespace(os.path.join(folder,'emutemps_'+SimAggr.building+'_'+sim_id+'_'+opt_start_str.replace('/','-').replace(':','-').replace(' ','-')), emutemps)
                store_namespace(os.path.join(folder,'mpctemps_'+SimAggr.building+'_'+sim_id+'_'+opt_start_str.replace('/','-').replace(':','-').replace(' ','-')), mpctemps)
                store_namespace(os.path.join(folder,'power_'+SimAggr.building+'_'+sim_id+'_'+opt_start_str.replace('/','-').replace(':','-').replace(' ','-')), power)
                store_namespace(os.path.join(folder,'controlseq_'+SimAggr.building+'_'+sim_id+'_'+opt_start_str.replace('/','-').replace(':','-').replace(' ','-')), controlseq)
                break
            except:
                print('%%%%%%%%%%%%%%%%%% Failed, trying again! %%%%%%%%%%%%%%%%%%%%%%')
                continue