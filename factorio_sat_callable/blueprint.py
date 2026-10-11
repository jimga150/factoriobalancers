from factorio_sat.blueprint import *

def blueprint_encode(args: str | list[str], label: str = '', level: str = 'normal') -> list[str]:
    ans = []

    if type(args) is str:
        args = [args]

    for arg in args:
        tiles = np.array(json.loads(arg))
        tiles = np.vectorize(read_tile)(tiles)
        ans.append(encode_blueprint(make_blueprint(tiles, label, TransportBeltLevel[level.upper()])))

    return ans

def blueprint_decode(args: str | list[str]) -> list[str]:
    ans = []

    if type(args) is str:
        args = [args]

    for arg in args:
        decoded = decode_blueprint(arg)
        # print(decoded)
        tiles = np.vectorize(write_tile)(import_blueprint(decoded))
        ans.append(json.dumps(tiles.tolist()))

    return ans

if __name__ == '__main__':
    main()
