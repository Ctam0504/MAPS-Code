/**
 * minunit.h - Minimal Unit Testing Framework for C projects.
 * Clean, portable, single-header framework.
 */
#ifndef MINUNIT_H
#define MINUNIT_H

#include <stdio.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif

extern int minunit_run;
extern int minunit_assert;
extern int minunit_fail;

#define MU_TEST(method_name) static void method_name(void)
#define MU_TEST_SUITE(suite_name) static void suite_name(void)

#define MU_RUN_TEST(test) do { \
    minunit_run++; \
    test(); \
} while (0)

#define mu_assert(test, message) do { \
    minunit_assert++; \
    if (!(test)) { \
        minunit_fail++; \
        printf("[FAIL] Assertion failed at %s:%d: %s\n", __FILE__, __LINE__, message); \
    } \
} while (0)

#define mu_check(test) mu_assert(test, #test)

#define mu_assert_int_eq(expected, actual) do { \
    minunit_assert++; \
    int _exp = (int)(expected); \
    int _act = (int)(actual); \
    if (_exp != _act) { \
        minunit_fail++; \
        printf("[FAIL] %s:%d: Expected %d, but got %d\n", __FILE__, __LINE__, _exp, _act); \
    } \
} while (0)

#define mu_assert_double_eq(expected, actual) do { \
    minunit_assert++; \
    double _exp = (double)(expected); \
    double _act = (double)(actual); \
    double _diff = _exp - _act; \
    if (_diff < -0.0001 || _diff > 0.0001) { \
        minunit_fail++; \
        printf("[FAIL] %s:%d: Expected %f, but got %f\n", __FILE__, __LINE__, _exp, _act); \
    } \
} while (0)

#define mu_assert_string_eq(expected, actual) do { \
    minunit_assert++; \
    const char* _exp = (expected); \
    const char* _act = (actual); \
    if (strcmp(_exp, _act) != 0) { \
        minunit_fail++; \
        printf("[FAIL] %s:%d: Expected \"%s\", but got \"%s\"\n", __FILE__, __LINE__, _exp, _act); \
    } \
} while (0)

#define MU_RUN_SUITE(suite_name) int main(int argc, char *argv[]) { \
    (void)argc; (void)argv; \
    printf("=== [TEST SUITE START] ===\n"); \
    suite_name(); \
    printf("=== [TEST RESULTS] ===\n"); \
    printf("Tests run: %d, Assertions: %d, Failures: %d\n", minunit_run, minunit_assert, minunit_fail); \
    if (minunit_fail == 0) { \
        printf("[SUCCESS] ALL TEST CASES PASSED\n"); \
        return 0; \
    } else { \
        printf("[FAILED] SOME TESTS FAILED\n"); \
        return 1; \
    } \
}

#ifdef MINUNIT_IMPLEMENTATION
int minunit_run = 0;
int minunit_assert = 0;
int minunit_fail = 0;
#endif

#ifdef __cplusplus
}
#endif

#endif /* MINUNIT_H */
