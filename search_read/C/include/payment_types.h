#ifndef PAYMENT_TYPES_H
#define PAYMENT_TYPES_H

typedef enum {
    CURRENCY_USD,
    CURRENCY_VND
} Currency;

typedef struct {
    char request_id[32];
    double amount;
    Currency currency;
} PaymentRequest;

#endif
