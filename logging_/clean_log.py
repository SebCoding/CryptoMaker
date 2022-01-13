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
    with open(file_in, 'rw') as f_in, open(file_out, 'w') as f_out:
        x = f_in.read().replace('\r', '')
        lines = (line.rstrip() for line in f_in)  # All lines including the blank ones
        lines = (line for line in lines if line)  # Non-blank lines
        for line in lines:
            # print(line, end='')
            if 'Bot Running:' in line:
                # print(line)
                continue
            f_out.writelines(line+'\n')


if __name__ == '__main__':
    main()
