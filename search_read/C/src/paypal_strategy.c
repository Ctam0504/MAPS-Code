#include <stdio.h>
#include <string.h>
#include "payment_strategy.h"

int paypal_pay(const PaymentRequest* request, GatewayError* error) {
    if (request->amount <= 0) {
        error->error_code = 400;
        snprintf(error->message, sizeof(error->message), "Paypal: So tien khong hop le");
        return 0;
    }
    printf("Thanh toan Paypal thanh cong cho request %s\n", request->request_id);
    return 1;
}

PaymentStrategy create_paypal_strategy() {
    PaymentStrategy s;
    s.name = "Paypal";
    s.pay = paypal_pay;
    return s;
}
