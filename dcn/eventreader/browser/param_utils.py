# utilities for collecting and sanitizingparameters
# from request and nav root

import caldate


cal_params = {
    'mode': set(['month', 'week', 'day', 'upcoming']),
    'date': 'date',
    'org': 'int_list',
    'gcid': 'int',
    'public': set(['y', 'n', 'b']),
    'free': set(['y', 'n', 'b']),
    'common': set(['y', 'n', 'b']),
    'udf1': set(['y', 'n']),
    'udf2': set(['y', 'n']),
    'days': 'int',
    'eid': 'int',
    'public-show': set(['y', 'n']),
    'free-show': set(['y', 'n']),
    'nocat-display': set(['1']),
    }


def strToIntList(val):
    if type(val) == int:
        return [val]
    else:
        vlist = []
        for v in val.split(','):
            try:
                vlist.append(int(v))
            except ValueError:
                pass
        return vlist


def sanitizeParam(param_key, val):
    """ return a sanitized parameter value """

    if val is not None:
        constraint = cal_params.get(param_key)
        if constraint is not None:
            if constraint == 'date':
                try:
                    return caldate.parseDateString(val)
                except (TypeError, ValueError):
                    return None
            elif constraint == 'int':
                try:
                    return int(val)
                except ValueError:
                    return None
            elif constraint == 'int_list':
                return strToIntList(val)
            elif type(constraint) == set:
                s = val.strip().lower()
                if s in constraint:
                    return s
    return None


def sanitizeParamDict(params):
    """ make sure everything in the params dict is expected and
        in acceptable format."""

    for key in params.keys():
        val = sanitizeParam(key, params.get(key))
        if val is None:
            del params[key]
        else:
            params[key] = val
    return params


def getQueryParams(request):
    """ Examine the HTTP query and pick up params for cal display """

    params = {}
    form = request.form
    for key in cal_params:
        val = form.get(key, form.get('%s-calendar' % key, None))
        if val is not None:
            params[key] = val

    return sanitizeParamDict(params)


def getSiteParams(navigation_root):
    """ examine the attributes of the site nav root for params
        for cal """

    params = {}
    for key in cal_params.keys():
        val = getattr(navigation_root, key, None)
        if val is not None:
            params.setdefault(key, val)

    return sanitizeParamDict(params)


def consolidateParams(vals, svals):
    """ consolidate svals into vals with svals values winning """

    for key in svals:
        vals[key] = svals[key]
    return vals
