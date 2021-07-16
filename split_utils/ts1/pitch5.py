# Author: Botao Yu

# B S O P D P D O P D B S O P D
# B S O O B S O -> B S O P D P D O P D B S O P D
# B - B
# S - S
# O - O

def split_sequence(ls_list, min_target_len=None):
    src_idx = 0
    tgt_idx = 0
    src_list = []
    tgt_list = []
    align_list = []

    num_p = 0

    for token in ls_list:
        t0 = token[0]
        if t0 == 'b':
            src_list.append(token)
            tgt_list.append(token)
            align_list.append('%d-%d' % (src_idx, tgt_idx))
            src_idx += 1
            tgt_idx += 1
        elif t0 == 's':
            src_list.append(token)
            tgt_list.append(token)
            align_list.append('%d-%d' % (src_idx, tgt_idx))
            src_idx += 1
            tgt_idx += 1
        elif t0 == 'o':
            src_list.append(token)
            tgt_list.append(token)
            align_list.append('%d-%d' % (src_idx, tgt_idx))
            src_idx += 1
            tgt_idx += 1
        elif t0 == 'p':
            tgt_list.append(token)
            tgt_idx += 1
            num_p += 1
        elif t0 == 'd':
            tgt_list.append(token)
            tgt_idx += 1
        else:
            raise ValueError("Cannot process token: %s" % token)

    if len(tgt_list) == 0 or len(src_list) == 0:
        return None, None, None
    if min_target_len is not None and num_p < min_target_len:
        return None, None, None

    return src_list, tgt_list, align_list


def restore_encoding(generated_token_str_list):
    token_str_list = generated_token_str_list[:]
    return token_str_list
