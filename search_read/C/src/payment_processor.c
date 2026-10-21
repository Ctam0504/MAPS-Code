#include "payment_processor.h"

PaymentProcessor create_processor(PaymentStrategy strategy) {
    PaymentProcessor p;
    p.strategy = strategy;
    return p;
}

int processor_execute(PaymentProcessor* processor, const PaymentRequest* request, GatewayError* error) {
    return processor->strategy.pay(request, error);
}
