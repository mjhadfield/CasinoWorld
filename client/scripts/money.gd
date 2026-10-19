class_name Money
## Pence -> display text. Static so @tool controls can use it in the editor too.


## 123456 -> "£1,234.56"; with `short`, whole pounds drop the pence (500 -> "£5").
static func format(pence: int, short := false) -> String:
	var pounds := str(absi(pence) / 100)
	var grouped := ""
	for i in pounds.length():
		if i > 0 and (pounds.length() - i) % 3 == 0:
			grouped += ","
		grouped += pounds[i]
	var sign := "-" if pence < 0 else ""
	if short and pence % 100 == 0:
		return "%s£%s" % [sign, grouped]
	return "%s£%s.%02d" % [sign, grouped, absi(pence) % 100]


## +£5 / -£5 / £0, for results.
static func signed(pence: int) -> String:
	if pence > 0:
		return "+" + format(pence, true)
	return format(pence, true)
