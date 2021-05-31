import os
import json


def check_list_layers(list_to_check, valid_iterable=(list,)):
    if isinstance(list_to_check, valid_iterable):
        if len(list_to_check) == 0:
            return 1
        return check_list_layers(list_to_check[0]) + 1
    else:
        return 0


def ensure_file_dir_to_save(file_path):
    dir_name = os.path.dirname(file_path)
    if dir_name == '':
        dir_name = '.'
    os.makedirs(dir_name, exist_ok=True)


def load_list(file_path):
    lines = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for l in f:
            ls = l.strip()
            blank = ls == ''
            if blank:
                continue
            lines.append(ls)
    return lines


def dump_list(list_to_dump, file_path):
    ensure_file_dir_to_save(file_path)
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in list_to_dump:
            f.write(str(item) + '\n')


def load_lists(file_path, keep_full_dim=False):
    multi_encodings = []

    cur_file_encodings = []
    in_a_file = False
    with open(file_path, 'r', encoding='utf-8') as f:
        for l in f:
            ls = l.strip()
            blank = ls == ''

            if blank:  # 遇到空行
                if in_a_file:  # 在处理一个文件中
                    multi_encodings.append(cur_file_encodings)
                    cur_file_encodings = []
                    in_a_file = False
                else:  # 不在处理某一个文件
                    pass
            else:  # 不是空行
                ls_list = ls.split(' ')
                if in_a_file:
                    cur_file_encodings.append(ls_list)
                else:
                    in_a_file = True
                    cur_file_encodings.append(ls_list)

    if in_a_file:
        multi_encodings.append(cur_file_encodings)

    if not keep_full_dim:
        for _ in range(2):
            if len(multi_encodings) == 1:
                multi_encodings = multi_encodings[0]

    return multi_encodings


def dump_lists(lists, file_path, no_internal_blanks=False):
    ensure_file_dir_to_save(file_path)

    list_layers = check_list_layers(lists)
    assert 0 < list_layers <= 3, "The lists variable is not valid."
    add_layers = 3 - list_layers
    for idx in range(add_layers):
        lists = [lists]

    with open(file_path, 'w', encoding='utf-8') as f:
        len1 = len(lists)
        for idx1 in range(len1):
            item1 = lists[idx1]
            len2 = len(item1)
            for idx2 in range(len2):
                item2 = item1[idx2]  # 一个文件中的一行
                f.write(' '.join(item2) + '\n')
            if not no_internal_blanks and idx1 < len1 - 1:
                f.write('\n')


def get_file_paths(data_dir, file_list=None, suffix=None):
    file_path_list = []
    if file_list is None:
        for root_dir, dirs, files in os.walk(data_dir):
            for file_name in files:
                if suffix is not None and not file_name.endswith(suffix):
                    continue
                file_path = os.path.join(root_dir, file_name)
                file_path_list.append(file_path)
    else:
        if isinstance(file_list, str):
            if file_list.endswith('.json'):
                with open(file_list, 'r') as f:
                    file_list = json.load(f)
            else:
                file_list = load_list(file_list)
        for file_name in file_list:
            if suffix is not None and not file_name.endswith(suffix):
                continue
            file_path = os.path.join(data_dir, file_name)
            file_path_list.append(file_path)
    return file_path_list


def remove_internal_blanks(input_path, output_path):
    li = load_list(input_path)
    dump_list(li, output_path)
