import os

TESTS_DIR = os.path.dirname(__file__)
EXAMPLES = os.path.join(TESTS_DIR, "..", "examples")


def example_path(folder, name):
    return os.path.join(EXAMPLES, folder, name)


def read_example(folder, name):
    with open(example_path(folder, name), encoding="utf-8") as f:
        return f.read()


def list_examples(folder):
    return sorted(os.listdir(os.path.join(EXAMPLES, folder)))
