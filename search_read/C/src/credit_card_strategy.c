#include <stdio.h>
#include <string.h>
#include "payment_strategy.h"

int credit_card_pay(const PaymentRequest* request, GatewayError* error) {
    if (request->amount <= 0) {
        error->error_code = 400;
        snprintf(error->message, sizeof(error->message), "CreditCard: So tien khong hop le");
        return 0;
    }
    printf("Thanh toan CreditCard thanh cong cho request %s\n", request->request_id);
    return 1;
}

PaymentStrategy create_credit_card_strategy() {
    PaymentStrategy s;
    s.name = "CreditCard";
    s.pay = credit_card_pay;
    return s;
}
