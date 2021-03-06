'''
energy_hourly_CSV.py
--------------------

script to create CSV of energy values hourly for all circuits
will output CSV with
rows - individual circuits, identified by pin number
cols - credit sample for each date

warning, dates missing from all circuits to not appear in index
'''

# boolean to say if data is non-resetting on resetting
non_resetting_data = True

# these lines control whether or not all circuits are queried
filter_by_meter_list = True
meter_list = ['ml00', 'ml01', 'ml02', 'ml03', 'ml04', 'ml05', 'ml06', 'ml07', 'ml08']
#meter_list = ['ml05']

# get list of pins corresponding to meters in meter_list
import offline_gateway as og
circuit_dict_list = og.get_circuit_dict_list(mains=True)

# use subsample while debugging
#circuit_dict_list = circuit_dict_list[:20]

# choose method of labeling data
method = 'meter'
#method = 'pin'

columns = 'circuits'

import datetime as dt
date_start = dt.datetime(2012, 3, 1)
date_end   = dt.datetime(2012, 4, 1)

# place time series for credit of each pin in a dictionary
d = {}
for i, c in enumerate(circuit_dict_list):

    if not filter_by_meter_list or c['meter_name'] in meter_list:

        # generate appropriate dictionary key
        if method == 'meter':
            label = c['meter_name'] + '-' + c['ip_address'][-2:]
        if method == 'pin':
            label = c['pin']

        # query database and append to dictionary
        print 'querying for', i, 'th circuit =', label
        if non_resetting_data:
            d[label], error = og.get_daily_energy_for_circuit_id_nr(c['circuit_id'], date_start, date_end)
        else:
            d[label], error = og.get_daily_energy_for_circuit_id(c['circuit_id'], date_start, date_end)

# assemble dictionary into dataframe
import pandas as p
df = p.DataFrame(d)

# transpose dataframe and output to CSV
filename = 'energy_daily_' + str(date_start.year) + '-' + str(date_start.month)
filename += '_' + method + '.csv'

if columns == 'dates':
    df.T.to_csv(filename)
if columns == 'circuits':
    df.to_csv(filename)