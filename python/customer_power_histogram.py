# pulls all customer midnight samples and creates histogram
import sqlalchemy as sa

# create metadata object
metadata = sa.MetaData('postgres://postgres:postgres@localhost:5432/gateway')

# define table objects from database
vp = sa.Table('view_power', metadata, autoload=True)

# query database
query = sa.select([vp.c.power, vp.c.meter_name],
                   #whereclause = sa.and_(vp.c.ip_address == '192.168.1.200',
                   whereclause = sa.and_(vp.c.ip_address != '192.168.1.200',
                                       vp.c.power > 0))
print query

# stuff array
result = query.execute()

country = 'ml'
#country = 'ug'

power_list = []
for r in result:
    if country in r.meter_name:
        power_list.append(r.power)

# graph histogram
import matplotlib.pyplot as plt

f, ax = plt.subplots(1,1)
import numpy as np
#ax.hist(power_list, bins=np.linspace(0,4000,41), facecolor='#dddddd')
ax.hist(power_list, bins=np.linspace(0,50,51), facecolor='#dddddd')
#ax.hist(power_list)
ax.set_xlabel('Daily Electrical Energy Consumed (Wh)')
ax.set_ylabel('Number of Days Observed')
ax.set_title('Mali Daily Electricity Consumption')
#ax.set_title('Uganda Mains Electricity Consumption')
#f.savefig(country+'_mains_histogram.pdf')
f.savefig(country+'power_histogram.pdf')

#plt.show()