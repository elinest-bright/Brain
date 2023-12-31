package com.matthaigh27.chatgptwrapper.data.remote.responses

import com.google.gson.JsonElement

data class ApiResponse (
    val status_code: Int,
    val message: List<String>,
    val result: Result
)

