drop view view_meter;

create view view_meter as
select
    c.id as circuit_id,
    m.id as meter_id,
    m.name as meter_name,
    c.ip_address,
    c.pin
from circuit as c
join meter as m
on c.meter=m.id;