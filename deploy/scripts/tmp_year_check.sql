SELECT MIN(contract_year), MAX(contract_year), COUNT(DISTINCT contract_year)
FROM collective_transactions
WHERE building_key = '4aadb250e05177bf01c033fb4dc2469a4b88ed3800120400741416ef3a9b58f7'
  AND is_valid = true;
