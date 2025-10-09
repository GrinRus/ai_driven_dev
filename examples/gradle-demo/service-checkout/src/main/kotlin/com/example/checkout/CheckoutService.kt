package com.example.checkout

class CheckoutService {
    fun calculateTotal(items: List<Double>, discount: Double = 0.0): Double {
        require(discount in 0.0..1.0) { "Discount must be between 0 and 1" }
        val subtotal = items.sum()
        return subtotal * (1.0 - discount)
    }
}
