package com.example.checkout

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class CheckoutServiceTest {
    private val service = CheckoutService()

    @Test
    fun calculatesTotalWithoutDiscount() {
        val total = service.calculateTotal(listOf(10.0, 5.0))
        assertEquals(15.0, total)
    }

    @Test
    fun appliesDiscount() {
        val total = service.calculateTotal(listOf(20.0, 10.0), discount = 0.1)
        assertEquals(27.0, total, 0.0001)
    }

    @Test
    fun rejectsInvalidDiscount() {
        assertFailsWith<IllegalArgumentException> {
            service.calculateTotal(listOf(5.0), discount = 1.5)
        }
    }
}
