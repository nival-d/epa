import math



def as_string_selector(input, mode='', accuracy=2):
    if mode == 'as_string':
        return str(round(input, accuracy))
    else:
        return input


def dBtomWStr(db, accuracy=4) -> str:
    mW = math.pow(10, float(db)/10)
    return str(round(mW, accuracy))


def db_to_mw(db, accuracy=4, mode='') -> str:
    mW = math.pow(10, float(db)/10)
    return as_string_selector(mW, mode)


def mW_to_dbm(mw, accuracy=2):
    if isinstance(mw, str):
        mw = float(mw)
    dbm = 10 * math.log10(mw)
    return round(dbm, accuracy)


def return_sum_of_mw(mW_data: list, mode='', accuracy=4):
    if all([isinstance(x, str) for x in mW_data]):
        mW_data = [float(x) for x in mW_data]

    if all([isinstance(x, float) for x in mW_data]):
        if mode == 'as_string':
            return str(round(sum(mW_data), accuracy))
        else:
            print('returning the sum now')
            return sum(mW_data)


def return_sum_of_dbm(dB_data: list, mode=''):
    if all([isinstance(x, str) for x in dB_data]):
        dB_data = [float(x) for x in dB_data]
    if all([isinstance(x, float) for x in dB_data]):
        all_mw = [db_to_mw(x) for x in dB_data]
        return as_string_selector(mW_to_dbm(sum(all_mw)),  accuracy=4, mode=mode)

    else:
        raise Exception('Inconsistent data types')


def return_sum_of_mW_from_dbm(dbm_data: list, mode=''):
    mw_data = [db_to_mw(x) for x in dbm_data]
    mw_sum = return_sum_of_mw(mw_data)
    return as_string_selector(mw_sum, accuracy=4, mode=mode)


def return_sum_of_dbm_from_mw(mw_data: list, mode=''):
    mw_sum = return_sum_of_mw(mw_data)
    return as_string_selector(mW_to_dbm(mw_sum), accuracy=2, mode=mode)