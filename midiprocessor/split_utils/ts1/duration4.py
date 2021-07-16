# Author: Botao Yu

# B S O P D P D O P D B S O P D
# B P P P B P -> B S O P D P D O P D B S O P D
# B-B, P-O, P-P, P-D

def split_sequence(ls_list, min_target_len=None):
    src_idx = 0
    tgt_idx = 0
    src_list = []
    tgt_list = []
    align_list = []

    tgt_count = 0

    src_b = None
    tgt_b = None
    tgt_s = None
    tgt_o = None
    src_p = None
    tgt_p = None
    tgt_d = None

    for token in ls_list:
        t0 = token[0]
        if t0 == 'b':
            src_b = src_idx
            tgt_b = tgt_idx
            src_list.append(token)
            src_idx += 1
            tgt_list.append(token)
            tgt_idx += 1
            align_list.append('%d-%d' % (src_b, tgt_b))
        elif t0 == 's':
            tgt_s = tgt_idx
            tgt_list.append(token)
            tgt_idx += 1
        elif t0 == 'o':
            tgt_o = tgt_idx
            tgt_list.append(token)
            tgt_idx += 1
        elif t0 == 'p':
            src_p = src_idx
            tgt_p = tgt_idx
            src_list.append(token)
            src_idx += 1
            tgt_list.append(token)
            tgt_idx += 1
        elif t0 == 'd':
            tgt_d = tgt_idx
            tgt_list.append(token)
            tgt_idx += 1
            tgt_count += 1

            align_list.append('%d-%d' % (src_p, tgt_o))
            align_list.append('%d-%d' % (src_p, tgt_p))
            align_list.append('%d-%d' % (src_p, tgt_d))

        else:
            raise ValueError("Cannot process token: %s" % token)

    if len(tgt_list) == 0 or len(src_list) == 0:
        return None, None, None
    if min_target_len is not None and tgt_count < min_target_len:
        return None, None, None

    return src_list, tgt_list, align_list


def restore_encoding(generated_token_str_list):
    token_str_list = generated_token_str_list[:]

    return token_str_list
