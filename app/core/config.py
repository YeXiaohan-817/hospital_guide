# 智能路径算法配置
USER_WEIGHTS = {
    "wheelchair": {
        "base_speed": 0.6,
        "weights": {"stairs": 9999, "inaccessible": 9999, "slope": 2.0, "elevator": 0.8}
    },
    "emergency": {
        "base_speed": 1.5,
        "weights": {"stairs": 1.0, "crowded": 1.5, "waiting": 2.0, "shortest": 0.8}
    },
    "elderly": {
        "base_speed": 0.7,
        "weights": {"stairs": 3.0, "crowded": 2.0, "elevator": 0.7}
    },
    "normal": {
        "base_speed": 1.0,
        "weights": {"stairs": 1.2, "elevator": 1.0, "crowded": 1.3}
    }
}

PATH_TYPE_COSTS = {
    "corridor": 1.0,
    "elevator": 1.2,
    "stairs": 1.5,
    "ramp": 1.1,
    "escalator": 1.0
}