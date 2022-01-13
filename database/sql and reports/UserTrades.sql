select 
	ut.exec_id "Exec Id"
	, ord.order_id "Order Id"
	, c_ord.stop_order_id "Cond Order Id"
	, ord.created_time "Order Created"
	, ord.updated_time "Closed Time"
	, ut.trade_time_ms "Closed Time"
	, ut.exec_type "Exec Type"

from public."UserTrades" ut
left join public."Orders" ord on ut.order_id = ord.order_id
left join public."CondOrders" c_ord on ut.order_id = c_ord.stop_order_id
where ut.exec_type not in ('Funding')
order by ut.trade_time_ms desc