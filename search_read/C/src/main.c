#include <stdio.h>
#include "payment_types.h"
#include "payment_processor.h"

extern PaymentStrategy create_credit_card_strategy();

int main() {
    PaymentRequest req = {"REQ_001", 100.0, CURRENCY_USD};
    PaymentStrategy card_strat = create_credit_card_strategy();
    PaymentProcessor processor = create_processor(card_strat);

    GatewayError err;
    if (!processor_execute(&processor, &req, &err)) {
        printf("Loi [%d]: %s\n", err.error_code, err.message);
    }
    return 0;
}
