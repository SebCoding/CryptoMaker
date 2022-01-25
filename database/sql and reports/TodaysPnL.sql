select 
	"Pair"
	, Date("Closed") 
	, ROUND(cast(sum("P&L") as numeric), 2) "P&L"
from public."v_ClosedPNL"
where Date("Closed") = CURRENT_DATE
group by 
	"Pair"
	, Date("Closed") 
order by Date("Closed") desc

