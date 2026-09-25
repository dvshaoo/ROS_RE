with open('06_notes/athlete_base_methods_table.txt', 'r', encoding='utf-8') as f:
    for line in f:
        l = line.lower()
        if any(k in l for k in ('mall', 'convert', 'exchange', 'token', 'fragment', 'suit', 'buy')):
            print(line.strip())
