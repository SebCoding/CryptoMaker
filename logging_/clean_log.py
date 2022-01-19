import sys


def get_new_filename(name):
    try:
        dot_index = name.rindex('.')
    except ValueError:
        return name + 'clean'

    name = name[0:dot_index] + '_clean' + name[dot_index:]
    return name


def main():
    if len(sys.argv) < 2:
        print(f"Missing file argument. Usage: {sys.argv[0]} <file_name>")
        sys.exit(1)
    # print(get_new_filename(sys.argv[1]))

    file_in = sys.argv[1]
    file_out = get_new_filename(file_in)
    with open(file_in, 'r') as f_in, open(file_out, 'w') as f_out:

        line = f_in.readline()
        while line:
            if 'pybit' not in line and 'urllib3' not in line:
                f_out.writelines(line)
            line = f_in.readline()


if __name__ == '__main__':
    main()
