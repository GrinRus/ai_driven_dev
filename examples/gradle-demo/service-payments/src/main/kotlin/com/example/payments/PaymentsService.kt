package com.example.payments

class PaymentsService {
    fun maskCard(number: String): String {
        require(number.length >= 4) { "card number too short" }
        val visible = number.takeLast(4)
        return "**** **** **** $visible"
    }
}
