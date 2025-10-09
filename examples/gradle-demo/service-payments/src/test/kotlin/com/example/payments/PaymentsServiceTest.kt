package com.example.payments

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class PaymentsServiceTest {
    private val service = PaymentsService()

    @Test
    fun masksCardNumber() {
        val masked = service.maskCard("4111111111111111")
        assertEquals("**** **** **** 1111", masked)
    }

    @Test
    fun rejectsShortCardNumber() {
        assertFailsWith<IllegalArgumentException> {
            service.maskCard("123")
        }
    }
}
