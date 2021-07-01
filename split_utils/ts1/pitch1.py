# Author: Botao Yu


def split_sequence_pitch1(ls_list, min_target_len=None):
    src_idx = 0
    tgt_idx = 0
    src_list = []
    tgt_list = []
    align_list = []

    last_b = -1
    last_s = -1
    last_o = -1
    last_p = -1

    for token in ls_list:
        t0 = token[0]
        if t0 == 'b':
            last_b = src_idx
            src_list.append(token)
            src_idx += 1
        elif t0 == 's':
            last_s = src_idx
            src_list.append(token)
            src_idx += 1
        elif t0 == 'o':
            last_o = src_idx
            src_list.append(token)
            src_idx += 1
        elif t0 == 'p':
            last_p = tgt_idx
            tgt_list.append(token)
            tgt_idx += 1
        elif t0 == 'd':
            current_d = src_idx
            src_list.append(token)
            src_idx += 1

            align_list.append('%d-%d' % (last_b, last_p))
            align_list.append('%d-%d' % (last_s, last_p))
            align_list.append('%d-%d' % (last_o, last_p))
            align_list.append('%d-%d' % (current_d, last_p))
        else:
            raise ValueError("Cannot process token: %s" % token)

    if len(tgt_list) == 0 or len(src_list) == 0:
        return None, None, None
    if min_target_len is not None and len(tgt_list) < min_target_len:
        return None, None, None

    return src_list, tgt_list, align_list
