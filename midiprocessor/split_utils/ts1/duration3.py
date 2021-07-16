# Author: Botao Yu

# B S O P D P D O P D B S O P D
# P P P P -> B S O P D P D O P D B S O P D
# P - B
# P - S
# P - O
# P - P
# P - D

def split_sequence_duration3(ls_list, min_target_len=None):
    src_idx = 0
    tgt_idx = 0
    src_list = []
    tgt_list = []
    align_list = []

    last_o_token = None
    last_p_token = None

    tgt_b = None
    tgt_s = None
    tgt_o = None
    src_p = None
    tgt_p = None
    tgt_d = None

    for token in ls_list:
        t0 = token[0]
        if t0 == 'b':
            tgt_b = tgt_idx
            tgt_list.append(token)
            tgt_idx += 1
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
            tgt_list.append(token)
            src_idx += 1
            tgt_idx += 1
        elif t0 == 'd':
            tgt_d = tgt_idx
            tgt_list.append(token)
            tgt_idx += 1

            align_list.append('%d-%d' % (src_p, tgt_b))
            align_list.append('%d-%d' % (src_p, tgt_s))
            align_list.append('%d-%d' % (src_p, tgt_o))
            align_list.append('%d-%d' % (src_p, tgt_p))
            align_list.append('%d-%d' % (src_p, tgt_d))

        else:
            raise ValueError("Cannot process token: %s" % token)

    if len(tgt_list) == 0 or len(src_list) == 0:
        return None, None, None
    if min_target_len is not None and len(src_list) < min_target_len:
        return None, None, None

    return src_list, tgt_list, align_list
