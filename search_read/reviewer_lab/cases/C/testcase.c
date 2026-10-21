/* Test harness excerpt (not part of the project source workspace). */
PaymentRequest request = {"REQ_001", 100.0, CURRENCY_USD};
PaymentProcessor processor = create_processor(create_credit_card_strategy());
GatewayError error = {0};
assert(processor_execute(&processor, &request, &error) == 0);
