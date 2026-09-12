"""Explicit USD must not silently become native XNO. Entirely offline."""
import pytest
from x402.schemas import AssetAmount
from x402_nano_exact import ExactNanoScheme, xno_to_raw
from .test_scheme import make_server
from x402.schemas import ResourceConfig

@pytest.mark.parametrize('price', ['0.01 USD', '0.01 usd', '  0.01 UsD  ', '0.01\tUSD'])
def test_explicit_usd_requires_converter(price):
    with pytest.raises(ValueError, match='fiat price'):
        ExactNanoScheme().parse_price(price, 'nano:mainnet')

def test_declining_converter_does_not_enable_fiat_fallback():
    scheme = ExactNanoScheme().register_money_parser(lambda amount, network: None)
    with pytest.raises(ValueError, match='fiat price'):
        scheme.parse_price('2 USD', 'nano:mainnet')

@pytest.mark.parametrize('price', ['2 USD', '2 usd', '$2'])
def test_registered_converter_can_handle_both_usd_forms(price):
    seen = []
    def converter(amount, network):
        seen.append((amount, network))
        return AssetAmount(amount='123', asset='XNO')
    result = ExactNanoScheme().register_money_parser(converter).parse_price(price, 'nano:mainnet')
    assert result.amount == '123'
    assert seen == [('2', 'nano:mainnet')]

@pytest.mark.parametrize('price', ['0.01', '0.01 XNO', '0.01 xno', 0.01])
def test_native_price_forms_still_work(price):
    assert ExactNanoScheme().parse_price(price, 'nano:mainnet').amount == xno_to_raw('0.01')

def test_sdk_cannot_publish_usd_price_as_native_quote(pay_to):
    with pytest.raises(ValueError, match='fiat price'):
        make_server().build_payment_requirements(ResourceConfig(scheme='exact', network='nano:mainnet', pay_to=pay_to, price='0.01 USD'))
