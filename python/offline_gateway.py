'''
offline_gateway.py
==================

shared library for offline gateway
'''

'''
takes series of hourly data and subsamples by day
if midnight is less than 11pm it uses 11pm sample
otherwise it uses the midnight sample
'''
def get_daily_energy_from_hourly_energy(watthours):
    import datetime as dt
    import pandas as p

    if watthours == None:
        return None
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
        return gd
    else:
        # if no result return None
        return None

'''
convenience function to get daily energy
'''
def get_daily_energy_for_circuit_id(circuit_id, date_start, date_end):
    watthours = get_watthours_for_circuit_id(circuit_id, date_start, date_end)
    if watthours == None:
        return None
    daily_watthours = get_daily_energy_from_hourly_energy(watthours)
    if len(daily_watthours) > 0:
        return daily_watthours
    else:
        return None

'''
non-resetting
'''
def get_daily_energy_for_circuit_id_nr(circuit_id, date_start, date_end):
    watthours = get_watthours_for_circuit_id(circuit_id, date_start, date_end)
    if watthours == None:
        return None
    daily_watthours = get_daily_energy_from_hourly_energy_nr(watthours)
    if len(daily_watthours) > 0:
        return daily_watthours
    else:
        return None

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
        return gd
    else:
        return None

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
        return gd
    else:
        return None

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
        #ax[0].set_title(filename)

    # plot battery_voltage on axis 1
    battery_voltage = get_battery_voltage_for_meter_name(meter_name, date_start, date_end)
    if battery_voltage != None:
        ax[1].plot_date(battery_voltage.index, battery_voltage.values, 'ko-')
        ax[1].set_ylabel('Battery Voltage (V)')


    # calculate hourly power/energy
    if hourly_kwh != None:
        import pandas as p
        hourly_power = hourly_kwh.shift(-1, offset=p.DateOffset(hours=1)) - hourly_kwh

        ax[2].plot_date(hourly_power.index, hourly_power.values, 'ko')
        ax[2].set_ylabel('Average Power (kW)')

        # plot daily energy
        daily_energy = hourly_kwh.shift(-1, offset=p.DateOffset(days=1)) - hourly_kwh

        ax[3].plot_date(daily_energy.index, daily_energy.values, 'ko')
        ax[3].set_ylabel('Daily Energy (kWh)')

    # plot daily energy consumed by meter
    cid = get_circuit_id_for_mains(meter_name)
    mains_energy = get_watthours_for_circuit_id(cid, date_start, date_end)

    if mains_energy != None:
        ax[4].plot_date(mains_energy.index, mains_energy.values, 'ko')

    #plt.show()
    f.autofmt_xdate()
    f.savefig(filename)
    plt.close()
