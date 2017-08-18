def print_device_summary(dev):
    """Prints tables of the attrs, read, and configuration keys


    The print out of this is not stable, do not screen-scrape.

    Parameters
    ----------
    dev : Device
        The device to summarize
    """
    desc = dev.describe()
    config_desc = dev.describe_configuration()
    read_attrs = dev.read_attrs
    config_attrs = dev.configuration_attrs
    used_attrs = set(read_attrs + config_attrs)
    extra_attrs = [a for a in dev.signal_names
                   if a not in used_attrs]
    hints = getattr(dev, 'hints', {}).get('fields', [])

    def print_leaf(a):
        s = getattr(dev, a)
        print(f'{a:<20} {type(s).__name__:<20}({s.name!r})')

    print()
    print('data keys (* hints)')
    print('-------------------')
    for k in sorted(desc):
        print('*' if k in hints else ' ', k)
    print()

    print('read attrs')
    print('----------')
    for a in read_attrs:
        print_leaf(a)

    print()
    print('config keys')
    print('-----------')
    for k in sorted(config_desc):
        print(k)
    print()

    print('configuration attrs')
    print('----------')
    for a in config_attrs:
        print_leaf(a)
    print()

    print('Unused attrs')
    print('------------')
    for a in extra_attrs:
        print_leaf(a)
