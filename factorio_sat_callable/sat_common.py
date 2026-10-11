def parse_network_str(net_str: str) -> list[tuple[int, int]]:
    network = []
    for line in net_str.splitlines():
        line = line.strip()
        if len(line) == 0:
            continue

        if line.startswith('#'):
            continue

        colours = [int(colour) for colour in line.split()]

        for i, colour in enumerate(colours):
            if colour == -1:
                colours[i] = None

        if len(colours) != 4:
            raise ValueError('Invalid network string')
        network.append((tuple(colours[:2]), tuple(colours[2:])))
    return network