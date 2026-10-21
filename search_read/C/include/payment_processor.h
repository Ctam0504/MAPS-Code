#ifndef PAYMENT_PROCESSOR_H
#define PAYMENT_PROCESSOR_H

#include "payment_strategy.h"

typedef struct {
    PaymentStrategy strategy;
} PaymentProcessor;

PaymentProcessor create_processor(PaymentStrategy strategy);
int processor_execute(PaymentProcessor* processor, const PaymentRequest* request, GatewayError* error);

#endif
