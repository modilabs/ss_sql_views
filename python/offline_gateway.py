'''
offline_gateway.py
==================

shared library for offline gateway
'''

import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import pandas as p

'''
takes series of hourly data and subsamples by day
if midnight is less than 11pm it uses 11pm sample
otherwise it uses the midnight sample
'''
def get_daily_energy_from_hourly_energy(watthours):
    import datetime as dt
    import pandas as p

    #if watthours == None:
    #    return None
    # create series with date-only index for 23 sample
    wh23 = watthours[[True if i.hour == 23 else False for i in watthours.index]]
    in23 = [dt.datetime(i.year, i.month, i.day) for i in wh23.index]
    wh23 = p.Series(data=wh23.values, index=in23)

    # create series with day-before date-only index for midnight sample
    wh24 = watthours[[True if i.hour == 0 else False for i in watthours.index]]
    in24 = [dt.datetime(i.year, i.month, i.day) - dt.timedelta(days=1) for i in wh24.index]
    wh24 = p.Series(data=wh24.values, index=in24)

    # take midnight sample only if greater or equal to 11pm sample
    combiner = lambda x, y: x if x >= y else y
    daily_watthours = wh24.combine(wh23, combiner)

    # filter NaN from result
    daily_watthours = daily_watthours.dropna()

    return daily_watthours

'''
non-resetting
'''
def get_daily_energy_from_hourly_energy_nr(watthours):
    import datetime as dt
    import pandas as p

    # filter NaN from result
    daily_watthours = watthours.shift(-1, offset=p.DateOffset(days=1)) - watthours

    daily_watthours = daily_watthours[[True if i.hour == 0 else
                                       False for i in daily_watthours.index]]

    return daily_watthours

'''
get_circuit_id_for_mains
'''
def get_circuit_id_for_mains(meter_name):
    import sqlalchemy as sa
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_meter', metadata, autoload=True )
    query = sa.select([t.c.circuit_id],
                       whereclause=sa.and_(t.c.ip_address == '192.168.1.200',
                                           t.c.meter_name == meter_name))
    result = query.execute()
    return result.first().circuit_id

'''
returns list of pins for circuits in meter_list
'''
def get_pins(meter_list):
    import sqlalchemy as sa
    import pandas as p
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_meter', metadata, autoload=True)
    q = sa.select([t.c.pin],
                   whereclause=sa.and_(t.c.meter_name.in_(meter_list),
                                       t.c.ip_address!='192.168.1.200'))
    result = q.execute()

    pl = [r.pin for r in result]
    return pl

'''
takes pin and dates as input
returns pandas series of credit with dates as index
'''
def get_credit_for_pin(pin, date_start, date_end):
    import sqlalchemy as sa
    import pandas as p

    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_midnight', metadata, autoload=True)

    q = sa.select([t.c.meter_timestamp,
                   t.c.credit],
                   whereclause=sa.and_(t.c.meter_timestamp >= date_start,
                                       t.c.meter_timestamp < date_end,
                                       t.c.pin == pin),
                   order_by=t.c.meter_timestamp,
                   distinct=True)
    result = q.execute()

    gd = p.DataFrame(result.fetchall(), columns=result.keys())
    gd = p.Series(gd['credit'], index=gd['meter_timestamp'])

    return gd

'''
takes circuit_id and returns pandas series for watthours
between date_start and date_end

warning - does not gracefully handle empty query result
'''
def get_watthours_for_circuit_id(circuit_id, date_start, date_end):
    import sqlalchemy as sa
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_primary_log', metadata, autoload=True)
    # the maximum and group by is a hack to get around duplicates
    query = sa.select([sa.func.max(t.c.watthours).label('watthours'),
                       t.c.meter_timestamp],
                       whereclause=sa.and_(t.c.circuit_id==circuit_id,
                                           t.c.meter_timestamp<=date_end,
                                           t.c.meter_timestamp>date_start),
                       order_by=t.c.meter_timestamp,
                       group_by=t.c.meter_timestamp,
                       distinct=True)
    result = query.execute()
    # check if query result is empty before attempting to create series
    fetchall = result.fetchall()
    if len(fetchall) > 0:
        import pandas as p
        gd = p.DataFrame(fetchall, columns=result.keys())
        gd = p.Series(gd['watthours'], index=gd['meter_timestamp'])
        return gd, 0
    else:
        # if no result return None
        return [], -1

'''
convenience function to get daily energy
'''
def get_daily_energy_for_circuit_id(circuit_id, date_start, date_end):
    watthours, error = get_watthours_for_circuit_id(circuit_id, date_start, date_end)
    #if watthours == None:
    if error == -1:
        return 0, -1
    daily_watthours = get_daily_energy_from_hourly_energy(watthours)
    if len(daily_watthours) > 0:
        return daily_watthours, 0
    else:
        return daily_watthours, -1

'''
returns a pandas series of the energy consumed over each hour
in the index
'''
def get_hourly_energy_for_circuit_id(circuit_id, date_start, date_end):
    watthours, error = get_watthours_for_circuit_id(circuit_id, date_start, date_end)
    # if error from get_watthours return None and error, else calculate hourly_energy
    if error == 0:
        import pandas as p
        hourly_energy = watthours.shift(-1, offset=p.DateOffset(hours=1)) - watthours
    else:
        return None, -1
    if len(hourly_energy) > 0:
        return hourly_energy, 0
    else:
        return None, -1

'''
non-resetting
'''
def get_daily_energy_for_circuit_id_nr(circuit_id, date_start, date_end):
    watthours, error = get_watthours_for_circuit_id(circuit_id, date_start, date_end)
    #if watthours == None:
    if error != 0:
        import pandas as p
        return p.Series([], index=[]), -1
    daily_watthours = get_daily_energy_from_hourly_energy_nr(watthours)
    if len(daily_watthours) > 0:
        return daily_watthours, 0
    else:
        return daily_watthours, -1

'''
returns credit for given circuit_id
'''
def get_credit_for_circuit_id(circuit_id, date_start, date_end):
    import sqlalchemy as sa
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_primary_log', metadata, autoload=True)
    query = sa.select([sa.func.max(t.c.credit).label('credit'),
                       t.c.meter_timestamp],
                       whereclause=sa.and_(t.c.circuit_id==circuit_id,
                                           t.c.meter_timestamp<=date_end,
                                           t.c.meter_timestamp>date_start),
                       order_by=t.c.meter_timestamp,
                       group_by=t.c.meter_timestamp,
                       distinct=True)
    result = query.execute()
    # check if query result is empty before attempting to create series
    fetchall = result.fetchall()
    if len(fetchall) > 0:
        import pandas as p
        gd = p.DataFrame(fetchall, columns=result.keys())
        gd = p.Series(gd['credit'], index=gd['meter_timestamp'])
        return gd
    else:
        return None

'''
gets circuit list for all circuits in database
returns list of tuples with (circuit_id, meter_name, ip_address)
'''
def get_circuit_list():
    import sqlalchemy as sa
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    vm = sa.Table('view_meter', metadata, autoload=True )
    # get list of circuits
    query = sa.select([vm.c.circuit_id,
                       vm.c.meter_name,
                       vm.c.ip_address],
                       order_by=(vm.c.meter_name, vm.c.ip_address)
                       )
    result = query.execute()
    circuit_list = []
    for r in result:
        circuit_list.append((r.circuit_id, r.meter_name, r.ip_address))
    return circuit_list

'''
returns a list of dictionaries for every circuit in the database
'''
def get_circuit_dict_list(mains=True):
    import sqlalchemy as sa
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    vm = sa.Table('view_meter', metadata, autoload=True )
    # get list of circuits
    if mains:
        query = sa.select([vm.c.circuit_id,
                           vm.c.meter_name,
                           vm.c.ip_address,
                           vm.c.pin],
                           order_by=(vm.c.meter_name, vm.c.ip_address)
                           )
    else:
        query = sa.select([vm.c.circuit_id,
                           vm.c.meter_name,
                           vm.c.ip_address,
                           vm.c.pin],
                           whereclause=vm.c.ip_address != '192.168.1.200',
                           order_by=(vm.c.meter_name, vm.c.ip_address)
                           )
    result = query.execute()
    circuit_dict_list = []
    for r in result:
        circuit_dict_list.append({'circuit_id':r.circuit_id,
                                  'meter_name':r.meter_name,
                                  'ip_address':r.ip_address,
                                  'pin':r.pin})
    return circuit_dict_list

'''
takes pin and dates as input
returns pandas series of credit with dates as index
'''
def get_energy_for_pin(pin, date_start, date_end):
    import sqlalchemy as sa
    import pandas as p

    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_primary_log', metadata, autoload=True)

    q = sa.select([t.c.meter_timestamp,
                   t.c.watthours],
                   whereclause=sa.and_(t.c.meter_timestamp >= date_start,
                                       t.c.meter_timestamp < date_end,
                                       t.c.pin == pin),
                   order_by=t.c.meter_timestamp,
                   distinct=True)
    result = q.execute()

    gd = p.DataFrame(result.fetchall(), columns=result.keys())
    gd = p.Series(gd['watthours'], index=gd['meter_timestamp'])

    return gd

def get_solar_kwh_for_meter_name(meter_name, date_start, date_end):
    import sqlalchemy as sa
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_solar', metadata, autoload=True)
    query = sa.select([t.c.solar_kwh, t.c.meter_timestamp],
                       whereclause=sa.and_(t.c.meter_name==meter_name,
                                           t.c.meter_timestamp<=date_end,
                                           t.c.meter_timestamp>date_start),
                       order_by=t.c.meter_timestamp)
    result = query.execute()
    # check for empty result
    fetchall = result.fetchall()
    if len(fetchall) > 0:
        import pandas as p
        gd = p.DataFrame(fetchall, columns=result.keys())
        gd = p.Series(gd['solar_kwh'], index=gd['meter_timestamp'])
        return gd, 0
    else:
        return None, -1

def get_battery_voltage_for_meter_name(meter_name, date_start, date_end):
    import sqlalchemy as sa
    metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')
    t = sa.Table('view_solar', metadata, autoload=True)
    query = sa.select([t.c.battery_volts, t.c.meter_timestamp],
                       whereclause=sa.and_(t.c.meter_name==meter_name,
                                           t.c.meter_timestamp<=date_end,
                                           t.c.meter_timestamp>date_start),
                       order_by=t.c.meter_timestamp)
    result = query.execute()
    # check for empty result
    fetchall = result.fetchall()
    if len(fetchall) > 0:
        import pandas as p
        gd = p.DataFrame(fetchall, columns=result.keys())
        gd = p.Series(gd['battery_volts'], index=gd['meter_timestamp'])
        return gd, 0
    else:
        return None, -1

def analyze_load_profile_curve(circuit_id, date_start, date_end):
    #capacity = ldc.max()   # if capacity relative to max of ldc
    capacity = 750.          # if capacity relative to rated power of inverter

    df, error = get_watthours_for_circuit_id(circuit_id, date_start, date_end)

    if error != 0:
        return
    # calculate discrete derivative
    import pandas as p
    offset = df - df.shift(1, offset=p.DateOffset(hours=1))

    positive_only = True
    #positive_only = False
    if positive_only:
        offset = offset[offset.values >= 0]

    threshold_spurious = True
    if threshold_spurious:
        offset = offset[offset.values <= capacity]

    # order values
    offset.sort()

    # create new series without date index but ordinal index
    ldc = p.Series(offset.values)


    #print ldc.sum()
    #print len(ldc)
    #print capacity * len(ldc)
    #print 'utilization factor', ldc.sum() / capacity / len(ldc)
    d = {'total_watthours':ldc.sum(),
         'total_hours':len(ldc),
         'capacity_factor':ldc.sum() / capacity / len(ldc),
         'circuit_id':circuit_id}
    return d

def plot_solar_all(meter_name, date_start, date_end):
    filename = 'psa-' + meter_name + '.pdf'
    print 'querying for ' + filename


    # plot each circuit daily energy values for all time
    import matplotlib.pyplot as plt
    f, ax = plt.subplots(6, 1, sharex=True, figsize=(8,12))

    # plot hourly_kwh on axis 0
    hourly_kwh = get_solar_kwh_for_meter_name(meter_name, date_start, date_end)
    if hourly_kwh != None:
        ax[0].plot_date(hourly_kwh.index, hourly_kwh.values, 'ko-')
        #ax[0].set_xlabel('Date')
        ax[0].set_ylabel('Delivered Energy (kWh)')
        ax[0].set_xlim((date_start, date_end))
        ax[0].grid(True)
        #ax[0].set_title(filename)

    # plot battery_voltage on axis 1
    battery_voltage = get_battery_voltage_for_meter_name(meter_name, date_start, date_end)
    if battery_voltage != None:
        ax[1].plot_date(battery_voltage.index, battery_voltage.values, 'ko-')
        ax[1].set_ylabel('Battery Voltage (V)')
        ax[1].grid(True)

    # calculate hourly power/energy
    if hourly_kwh != None:
        import pandas as p
        hourly_power = hourly_kwh.shift(-1, offset=p.DateOffset(hours=1)) - hourly_kwh

        ax[2].plot_date(hourly_power.index, hourly_power.values, 'ko')
        ax[2].set_ylabel('Average Power (kW)')
        ax[2].grid(True)
        # plot daily energy
        daily_energy = hourly_kwh.shift(-1, offset=p.DateOffset(days=1)) - hourly_kwh

        ax[3].plot_date(daily_energy.index, daily_energy.values, 'ko')
        ax[3].set_ylabel('Daily Energy (kWh)')
        ax[3].grid(True)
    # plot daily energy consumed by meter
    cid = get_circuit_id_for_mains(meter_name)
    mains_energy = get_watthours_for_circuit_id(cid, date_start, date_end)

    if mains_energy != None:
        ax[4].plot_date(mains_energy.index, mains_energy.values, 'ko')
        ax[4].grid(True)
    #plt.show()
    f.suptitle(meter_name)
    f.autofmt_xdate()
    f.savefig(filename)
    plt.close()

def plot_power(circuit_id,
               date_start,
               date_end,
               filename='default_plot_power.pdf',
               title=None):
    '''
    plot_power
    ==========
    outputs
    -------
    raw timeseries plot of hourly power demand for a specified circuit

    inputs
    ------
    circuit_id : integer specifying database id for circuit
    date_start : datetime object that describes start of data
    date_end   : datetime object that describes end of data
    filename   : string specifying name of output file
    annotate   : boolean for output annotation on plot
    title      : string that will be used as title for plot
    '''

    # get energy for circuit_id and daterange, return -1 on empty dataframe
    hourly_energy, error = get_watthours_for_circuit_id(circuit_id, date_start, date_end)
    if error != 0:
        return -1

    # calculate hourly power/energy using pandas shift
    hourly_power = hourly_energy.shift(-1, offset=p.DateOffset(hours=1)) - hourly_energy

    # create and label plot
    f, ax = plt.subplots(1, 1)
    ax.plot_date(hourly_power.index, hourly_power.values, 'k')
    ax.set_ylabel('Average Power (W)')
    ax.set_ylim(ymin=0)
    ax.grid(True)
    f.autofmt_xdate()

    # title plot if argument supplied by caller
    if title != None:
        ax.set_title(title)

    # save figure to file
    f.savefig(filename)

def plot_hourly_power_profile(circuit_id, date_start, date_end, filename, title=True):
    '''
    plots superimposed hourly profile
    '''
    import matplotlib.pyplot as plt
    import datetime as dt
    df = get_watthours_for_circuit_id(circuit_id, date_start, date_end)
    df = df[0]
    # offset by 1 hour and subtract
    import pandas as p
    offset = df.shift(-1, offset=p.DateOffset(hours=1)) - df

    # screen out negative values resulting from drops
    positive_only = True
    if positive_only:
        offset = offset[offset.values >= 0]

    # extract hour information from series index for plotting
    hour = [ind.hour for ind in offset.index]

    # plotting of hour vs. power values to create profile
    f = plt.figure()
    ax = f.add_axes((0.2,0.2,0.6,0.6))
    ax.plot(hour, offset.values, linestyle='',
            marker='o', mec='#ffffff', alpha=0.2, mfc=None)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Average Hourly Power (W)')
    ax.set_xticks((0,4,8,12,16,20,24))
    ax.set_xlim((-1, 25))
    if title:
        ax.set_title(filename)

    # add annotations to plot
    annotation = []
    annotation.append('plot generated ' + str(dt.datetime.now()))
    annotation.append('date start = ' + str(date_start))
    annotation.append('date end = ' + str(date_end))
    annotation = '\n'.join(annotation)
    f.text(0.01,0.01, annotation)

    # save to file
    f.savefig(filename, transparent=True)
    plt.close()

def plot_load_profile_curve_to_axis(circuit_id, date_start, date_end, ax, title=False, label=None):
    df, error = get_watthours_for_circuit_id(circuit_id, date_start, date_end)

    if error != 0:
        return
    # calculate discrete derivative
    import pandas as p
    offset = df - df.shift(1, offset=p.DateOffset(hours=1))

    positive_only = True
    #positive_only = False
    if positive_only:
        offset = offset[offset.values >= 0]

    threshold_spurious = True
    if threshold_spurious:
        offset = offset[offset.values <= 700]

    # order values
    offset.sort()

    # create new series without date index but ordinal index
    ldc = p.Series(offset.values[::-1])

    # plot normalized ordinal index against values
    ax.plot([float(i)/len(offset) for i in ldc.index], ldc.values, label=label)
    #ax.set_xlabel('Date')
    ax.set_ylabel('Average Hourly Power')
    ax.set_ylim(ymin=0, ymax=400)
    if title:
        ax.set_title(filename)

def plot_load_profile_curve_to_file(circuit_id, date_start, date_end, filename, title=False):

    # plot each circuit daily energy values for all time
    f, ax = plt.subplots(1, 1, sharex=True)
    plot_load_profile_curve_to_axis(circuit_id, date_start, date_end, ax, title)
    f.savefig(filename)
    plt.close()

def plot_date_fit(df, ax):
    timestamp = np.array(df.index)
    values = np.array(df.values)

    date_minimum = min(timestamp)
    date_maximum = max(timestamp)

    timestamp = [(ms-date_minimum).total_seconds() for ms in timestamp]
    p = np.polyfit(timestamp, values, 1)

    output_string = '%.1f per day' % (p[0] * 3600 * 24)
    #print meter_name, output_string#'%.1f' % (p[0] * 3600 * 24), 'kWh per day'
    ax.text(0.05, 0.7, output_string, transform=ax.transAxes)
    fit_timebase = np.linspace(0, (date_maximum-date_minimum).total_seconds(), 10)
    fit_energy = np.polyval(p, fit_timebase)
    fit_timebase = [date_minimum + dt.timedelta(seconds=ft) for ft in fit_timebase]

    ax.plot_date(fit_timebase, fit_energy, 'k')

    print p
    return p

def plot_customer_energy_histogram(meter_list=['ml01', 'ml02', 'ml03', 'ml04', 'ml05', 'ml06', 'ml07', 'ml08'],
                                   date_start=dt.datetime(2012, 1, 1),
                                   date_end=dt.datetime(2012, 2, 1),
                                   filename='default_histogram.pdf',
                                   annotate=False,
                                   remove_zeros=True,
                                   title=None):
    '''
    customer_energy_histogram.py
    ============================
    outputs
    -------
    a histogram displaying the frequency of customer daily energy values for
    a list of meters.

    inputs
    ------
    meter_list : list of strings describing meter_name identifier in database
    date_start : datetime object that describes start of data
    date_end   : datetime object that describes end of data
    filename   : string specifying name of output file
    annotate   : boolean for output annotation on plot
    remove_zeros : boolean to control removal of zero consumption from histogram
    title : string that will be used as title for plot
    '''

    # select all circuits from database (we will later filter)
    circuit_dict_list = get_circuit_dict_list(mains=False)

    # get daily energy for each circuit
    all_energy = p.Series()
    all_energy = np.array([])
    num_circuits = 0

    # iterate over circuit_dict_list and skip meters not in meter_list
    for cd in circuit_dict_list:
        if cd['meter_name'] not in meter_list:
            continue
        print cd['circuit_id']
        num_circuits += 1
        de, err = get_daily_energy_for_circuit_id(cd['circuit_id'], date_start, date_end)
        if err != 0:
            continue
        all_energy = np.hstack((all_energy, de.values))

    # remove any days of zero consumption from array and histogram
    if remove_zeros:
        all_energy = all_energy[all_energy > 0]

    # plot histogram
    import matplotlib.pyplot as plt
    f = plt.figure()

    # set plot boundary appropriately to make room for annotation
    if annotate:
        ax = f.add_axes((0.2,0.3,0.6,0.6))
    else:
        ax = f.add_axes((0.1, 0.1, 0.85, 0.8))

    # plot and set labels
    ax.hist(all_energy, bins=np.linspace(0,200,41), facecolor='#dddddd', normed=True)
    ax.set_xlabel('Daily Electrical Energy Consumed (Wh)')
    ax.set_ylabel('Frequency of Observation')
    if title != None:
        ax.set_title(title)

    # create metadata and plot to stdout
    annotation = []
    annotation.append('plot generated ' + str(dt.datetime.now()))
    annotation.append('date start = ' + str(date_start))
    annotation.append('date end = ' + str(date_end))
    annotation.append('meter list = ' + str(meter_list))
    annotation = '\n'.join(annotation)
    print annotation
    print 'number of datapoints = ', len(all_energy)
    print 'possible observations = ', num_circuits * (date_end - date_start).days

    # add metadata to plot
    if annotate:
        f.text(0.01, 0.01, annotation)

    # save to file
    f.savefig(filename)