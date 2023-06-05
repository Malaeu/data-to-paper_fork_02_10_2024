import pytest

from scientistgpt.utils.check_numeric_values import extract_numeric_values, find_non_matching_numeric_values, \
    add_one_to_last_digit


@pytest.mark.parametrize('text, numbers', [
    ('The p-value was 1.02 and the variance was 10.00', ['1.02', '10.00']),
    ('Number can be writen with a comma 200,000 or not 100123', ['200,000', '100123']),
    ('There were three numbers 10, 3 and 9', ['10', '3', '9']),
    ('Some results can be negative, like -100.2', ['-100.2']),
])
def test_extract_numeric_values(text, numbers):
    assert extract_numeric_values(text) == numbers


@pytest.mark.parametrize('x, y', [
    ('123', '124'),
    ('123.4', '123.5'),
    ('1099', '1100'),
    ('10.99', '11.00'),
    ('99.99', '100.00'),
])
def test_add_one_to_last_digit(x, y):
    assert add_one_to_last_digit(x) == y


@pytest.mark.parametrize('source, target, non_matching', [
    ('p-value 1.0187912, variance 10.0000001', 'p-value 1.02, variance 10.00', []),
    ('p-value 1.0187912, variance 10.0000001', 'p-value 1.01, variance 10.00', []),
    ('p-value 1.0137912, variance 10.0000001', 'p-value 1.02, variance 10.00', ['1.02']),
    ('p-value 1.0137912, variance 10.0000001', 'p-value 1.01, variance 10.00', []),
    ('p-value 1.0272333, variance 10.01', 'p-value 1.02, variance 10.00', []),
    ('p-value 1.0272333, variance 10.01', 'p-value 1.02, variance 10.001', ['10.001']),
    ('rows: 234091, cols: 9', 'We had 234,091 rows and 9 columns', []),
    ('accuracy of 0.900154, FDR 0.0021, AUC of 0.7524921', 'accuracy of 90.02%, AUC of 75.25% and FDR 0.2%', []),
    ('accuracy of 0.9002, FDR 0.0021, AUC of 0.7525', 'accuracy of 90.02%, AUC of 75.25% and FDR 0.2%', []),
])
def test_find_non_matching_numeric_values(source, target, non_matching):
    assert find_non_matching_numeric_values(source, target) == non_matching