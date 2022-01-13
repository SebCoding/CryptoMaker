select
	--cpnl.id "Id"
	ord.created_time "Created"
	, ord.updated_time "Closed"
	, case 
		when cpnl.side = 'Buy' then 'Long'
		when cpnl.side = 'Sell' then 'Short'
		else null
	  end "Side"
	, cpnl.order_type "Order Type"
	, ord.order_status "Status"
	, cpnl.qty "Open Size"
	, cpnl.closed_size "Closed Size"
	, cpnl.avg_entry_price "Avg Entry Price"
	, cpnl.avg_exit_price "Avg Exit Price"
	--, cpnl.order_price "Price"
	, cpnl.closed_pnl "P&L"
	, cpnl.leverage || 'x' "Leverage"
	--, cpnl.exec_type "Exit Type"
    , ord.order_id "Order Id"
from public."ClosedPnL" cpnl 
inner join public."Orders" ord on cpnl.order_id = ord.order_id

union 

select
	--cpnl.id "Id"
	c_ord.created_time "Created"
	, c_ord.updated_time "Closed"
	, case 
		when cpnl.side = 'Buy' then 'Long'
		when cpnl.side = 'Sell' then 'Short'
		else null
	  end "Side"
	, cpnl.order_type "Order Type"
	, c_ord.order_status "Status"
	, cpnl.qty "Open Size"
	, cpnl.closed_size "Closed Size"
	, cpnl.avg_entry_price "Avg Entry Price"
	, cpnl.avg_exit_price "Avg Exit Price"
	--, cpnl.order_price "Price"
	, cpnl.closed_pnl "P&L"
	, cpnl.leverage || 'x' "Leverage"
	--, cpnl.exec_type "Exit Type"
    , c_ord.stop_order_id "Order Id"
from public."ClosedPnL" cpnl 
inner join public."CondOrders" c_ord on cpnl.order_id = c_ord.stop_order_id

order by "Created" desc