'''
average_daily_customer_energy.py
================================

right now, this script is being used to create a csv that will be joined to survey data.

calculates average energy per circuit over data range.

can filter by country

currently ignoring zeros for every circuit and returns csv text dump

can direct text to file by calling script as ::

    python average_daily_customer_energy.py > outfile.csv

todo: add column for percentage of time with credit

todo: add column for energy consumption growth

'''

import sqlalchemy as sa
import datetime as dt

date_start = dt.datetime(2011,12,1)
date_end = dt.datetime(2011,12,31)

country_select = 'ml'
#country_select = 'ug'

meter_list = ('ml01', 'ml02', 'ml03', 'ml04', 'ml07', 'ml08')

# create metadata object
metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')

# define table objects from database
vm = sa.Table('view_midnight', metadata, autoload=True)

# get meter list from database
query = sa.select([vm.c.pin,
                   vm.c.meter_name,
                   vm.c.ip_address,
                   sa.func.avg(vm.c.watthours).over(partition_by=vm.c.circuit_id).label('myavg'),
                   sa.func.count(vm.c.watthours).over(partition_by=vm.c.circuit_id).label('mycount')
                   ],
                   whereclause=sa.and_(vm.c.watthours>0,
                                       vm.c.ip_address!='192.168.1.200',
                                       vm.c.meter_timestamp>date_start,
                                       vm.c.meter_timestamp<date_end,
                                       #vm.c.meter_name.like('%' + country_select + '%')
                                       vm.c.meter_name.in_(meter_list)
                   ),
                   distinct=True,
                   order_by=sa.desc('myavg')
                   )

#print query
result = query.execute()

# print result
daily_watthours = []
print 'pin, meter_name.ip_address, average_watthours, num_data_points'
for r in result:
    print r.pin + ',',
    print r.meter_name + '.' + r.ip_address[-3:] + ',',
    print '%.1f' % r.myavg + ',',
    print str(r.mycount)
    daily_watthours.append(r.myavg)

import numpy as np
daily_watthours = np.array(daily_watthours)
#print 'mean =', '%.1f' % daily_watthours.mean()
#print 'std  =', '%.1f' % daily_watthours.std()
