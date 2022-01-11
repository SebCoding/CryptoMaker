def init_status_bar(length):
    c = '#'
    bars = []
    for i in range(length+1):
        bar = '['
        for j in range(i):
            bar += c
        for j in range(i, length):
            bar += ' '
        bar += ']'
        bars.append(bar)
    bars[0] = ''
    return bars

print(init_status_bar(10))