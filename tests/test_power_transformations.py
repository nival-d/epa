import pytest
import power_analyser
import os

SAMPLE_DATA_DIR = 'sample_data'



@pytest.fixture()
def wrapper():
    wrapper = power_analyser.endpointRegister()
    yield wrapper


def test_update_link_register(wrapper):
    data = ('routerA', 'ifaceA', 'routerB', 'ifaceB')
    wrapper.update_link_register(*data)
    assert wrapper.link_register == [{'nodeA': 'routerA', 'ifaceA': 'ifaceA', 'nodeB': 'routerB', 'ifaceB': 'ifaceB'}]


def test_update_link_register_aux_data(wrapper):
    data = {'nodeA': 'routerA', 'ifaceA': 'ifaceA', 'nodeB': 'routerB', 'ifaceB': 'ifaceB', 'link_name':'link_name'}
    wrapper.update_link_register(**data)
    assert wrapper.link_register == [{'nodeA': 'routerA', 'ifaceA': 'ifaceA', 'nodeB': 'routerB',
                                      'ifaceB': 'ifaceB', 'link_name':'link_name'}]

def test_update_interface_register(wrapper):
    data = {'device': 'routerA', 'interface': 'ifaceA'}
    wrapper.update_interface_register(**data)
    print(wrapper.interface_register)
    assert wrapper.interface_register == {'routerA': {'ifaceA': {'ifname': 'ifaceA'}}}


def test_update_interface_register2(wrapper):
    data1 = {'device': 'routerA', 'interface': 'ifaceA'}
    data2 = {'device': 'routerA', 'interface': 'ifaceB'}
    data3 = {'device': 'routerB', 'interface': 'ifaceC'}
    wrapper.update_interface_register(**data1)
    wrapper.update_interface_register(**data2)
    wrapper.update_interface_register(**data3)
    print(wrapper.interface_register)
    assert wrapper.interface_register == {'routerA': {'ifaceA': {'ifname': 'ifaceA'},
                                                      'ifaceB': {'ifname': 'ifaceB'}},
                                          'routerB': {'ifaceC': {'ifname': 'ifaceC'}}}


def test_update_interface_register_duplicate(wrapper):
    data1 = {'device': 'routerA', 'interface': 'ifaceA'}
    data2 = {'device': 'routerA', 'interface': 'ifaceA'}
    wrapper.update_interface_register(**data1)
    with pytest.raises(Exception):
        wrapper.update_interface_register(**data2)

def test_xr_precise_controllers_parsing(wrapper):
    data= '''
Total Tx power: 2.91 mW (  4.65 dBm)
  Lane 0 Tx power: 0.74 mW ( -1.30 dBm)
  Lane 1 Tx power: 0.70 mW ( -1.54 dBm)
  Lane 2 Tx power: 0.73 mW ( -1.34 dBm)
  Lane 3 Tx power: 0.74 mW ( -1.31 dBm)
Total Rx power: 4.11 mW (  6.14 dBm)
  Lane 0 Rx power: 1.28 mW (  1.06 dBm)
  Lane 1 Rx power: 1.04 mW (  0.19 dBm)
  Lane 2 Rx power: 1.08 mW (  0.32 dBm)
  Lane 3 Rx power: 0.71 mW ( -1.48 dBm)'''
    result = wrapper.xr_precise_controllers_parsing(data)
    assert result['Tx']['total']['dBm'] == '4.65'
    assert result['Tx']['total']['mW'] == '2.91'
    assert result['Rx']['total']['dBm'] == '6.14'
    assert result['Rx']['total']['mW'] == '4.11'
    # a physically painful section
    assert result['Tx']['per_lane']['0']['dBm'] == '-1.30'
    assert result['Tx']['per_lane']['0']['mW'] == '0.74'
    assert result['Tx']['per_lane']['1']['dBm'] == '-1.54'
    assert result['Tx']['per_lane']['1']['mW'] == '0.70'
    assert result['Tx']['per_lane']['2']['dBm'] == '-1.34'
    assert result['Tx']['per_lane']['2']['mW'] == '0.73'
    assert result['Tx']['per_lane']['3']['dBm'] == '-1.31'
    assert result['Tx']['per_lane']['3']['mW'] == '0.74'
    assert len(result['Tx']['per_lane'].keys()) == 4

    assert result['Rx']['per_lane']['0']['dBm'] == '1.06'
    assert result['Rx']['per_lane']['0']['mW'] == '1.28'
    assert result['Rx']['per_lane']['1']['dBm'] == '0.19'
    assert result['Rx']['per_lane']['1']['mW'] == '1.04'
    assert result['Rx']['per_lane']['2']['dBm'] == '0.32'
    assert result['Rx']['per_lane']['2']['mW'] == '1.08'
    assert result['Rx']['per_lane']['3']['dBm'] == '-1.48'
    assert result['Rx']['per_lane']['3']['mW'] == '0.71'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_xr_simplified_controllers_parsing(wrapper):
    data = '''           Wavelength    Tx Power          Rx Power      Laser Bias
        Lane  (nm)    (dBm)    (mW)     (dBm)     (mW)      (mA)
        --   -----   ------   ------    ------   ------    ------
        1    0     2.2   1.6769     -1.1   0.2738     176.624
        2    0     1.4   1.3649     -3.3   0.0770     176.624
        3    0     2.5   1.7848     -3.5   0.1120     176.624
        4    0     2.8   1.8950     -6.2   0.6707     176.624'''

    result = wrapper.xr_simplified_controllers_parsing(data)

    assert str(round(result['Tx']['total']['mW'], 4)) == '6.7216'
    assert str(round(result['Rx']['total']['mW'], 4)) == '1.1335'

    # a physically painful section
    assert result['Tx']['per_lane']['0']['dBm'] == '2.2'
    assert result['Tx']['per_lane']['0']['mW'] == '1.6769'
    assert result['Tx']['per_lane']['1']['dBm'] == '1.4'
    assert result['Tx']['per_lane']['1']['mW'] == '1.3649'
    assert result['Tx']['per_lane']['2']['dBm'] == '2.5'
    assert result['Tx']['per_lane']['2']['mW'] == '1.7848'
    assert result['Tx']['per_lane']['3']['dBm'] == '2.8'
    assert result['Tx']['per_lane']['3']['mW'] == '1.8950'
    assert len(result['Tx']['per_lane'].keys()) == 4
    assert result['Rx']['per_lane']['0']['dBm'] == '-1.1'
    assert result['Rx']['per_lane']['0']['mW'] == '0.2738'
    assert result['Rx']['per_lane']['1']['dBm'] == '-3.3'
    assert result['Rx']['per_lane']['1']['mW'] == '0.0770'
    assert result['Rx']['per_lane']['2']['dBm'] == '-3.5'
    assert result['Rx']['per_lane']['2']['mW'] == '0.1120'
    assert result['Rx']['per_lane']['3']['dBm'] == '-6.2'
    assert result['Rx']['per_lane']['3']['mW'] == '0.6707'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_parsing_sample_output_simple_power_sample2(wrapper):
    test_file = 'power_sample2'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.xr_precise_controllers_parsing(data)
        # a physically painful section
        assert result['Tx']['per_lane']['0']['dBm'] == '1.86'
        assert result['Tx']['per_lane']['0']['mW'] == '1.54'
        assert result['Tx']['per_lane']['3']['dBm'] == '2.57'
        assert result['Tx']['per_lane']['3']['mW'] == '1.81'
        assert len(result['Tx']['per_lane'].keys()) == 4
        assert result['Rx']['per_lane']['0']['dBm'] == '-0.24'
        assert result['Rx']['per_lane']['0']['mW'] == '0.95'
        assert result['Rx']['per_lane']['3']['dBm'] == '1.14'
        assert result['Rx']['per_lane']['3']['mW'] == '1.30'
        assert len(result['Rx']['per_lane'].keys()) == 4


def test_parsing_sample_output_simple_power_sample3(wrapper):
    test_file = 'power_sample3'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.xr_simplified_controllers_parsing(data)
        # a physically painful section
        assert result['Tx']['per_lane']['0']['dBm'] == '2.2'
        assert result['Tx']['per_lane']['0']['mW'] == '1.6769'
        assert result['Tx']['per_lane']['3']['dBm'] == '2.8'
        assert result['Tx']['per_lane']['3']['mW'] == '1.8950'
        assert len(result['Tx']['per_lane'].keys()) == 4
        assert result['Rx']['per_lane']['0']['dBm'] == '-1.1'
        assert result['Rx']['per_lane']['0']['mW'] == '0.2738'
        assert result['Rx']['per_lane']['3']['dBm'] == '-6.2'
        assert result['Rx']['per_lane']['3']['mW'] == '0.6707'
        assert len(result['Rx']['per_lane'].keys()) == 4




