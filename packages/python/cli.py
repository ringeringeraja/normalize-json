#!/usr/bin/env python3

import json
import normalize.normalize as Normalize

def main(argv: list[str]):
    _, mapping, sample, *_ = argv
    with open(sample) as f_s, open(mapping) as f_m:
        sample = json.loads(f_s.read())
        mapping = json.loads(f_m.read())

        sample = Normalize.flatten(sample)
        result = Normalize.translate(sample, mapping)
        print(json.dumps(result, indent=2))

if __name__ == '__main__':
    from sys import argv
    main(argv)
