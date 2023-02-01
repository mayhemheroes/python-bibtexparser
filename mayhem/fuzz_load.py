#! /usr/bin/env python3
import atheris
import sys
import fuzz_helpers

with atheris.instrument_imports(include=[
    'bibtexparser',
    'bibtexparser.bibdatabase',
    'bibtexparser.bibtexexpression',
    'bibtexparser.bparser',
    'bibtexparser.bwriter',
    'bibtexparser.latexenc',
    'bibtexparser.customization',
    'bibtexparser.pybtexbridge',
    'bibtexparser.pybtexbridge.utils',
]):
    import bibtexparser


def TestOneInput(data):
    fdp = fuzz_helpers.EnhancedFuzzedDataProvider(data)
    if fdp.ConsumeBool():
        bibtexparser.loads(fdp.ConsumeRemainingString())
    else:
        with fdp.ConsumeMemoryFile(all_data=True, as_bytes=False) as f:
            bibtexparser.load(f)


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
