package com.example.claudio

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import retrofit2.Call

// Modelos de datos
data class RobotStatus(
    val homed: Boolean,
    val position: Position,
    val arm: ArmStatus,
    val gripper: String
)

data class Position(
    val x: Double,
    val y: Double
)

data class ArmStatus(
    val servo1: Int,
    val servo2: Int
)

data class ResponseMessage(
    val message: String,
    val success: Boolean,
    val data: Any?
)

data class MoveRequest(
    val x: Double,
    val y: Double
)

data class ArmMoveRequest(
    val servo1: Int,
    val servo2: Int,
    val time_ms: Int
)

// Interface de la API
interface RobotApiService {

    @GET("robot/status")
    fun getRobotStatus(): Call<RobotStatus>

    @POST("robot/move")
    fun moveToPosition(@Body request: MoveRequest): Call<ResponseMessage>

    @POST("robot/arm/move")
    fun moveArm(@Body request: ArmMoveRequest): Call<ResponseMessage>

    @POST("robot/arm/state/{state}")
    fun changeArmState(@Path("state") state: String): Call<ResponseMessage>

    @POST("robot/gripper/open")
    fun openGripper(): Call<ResponseMessage>

    @POST("robot/gripper/close")
    fun closeGripper(): Call<ResponseMessage>

    @POST("robot/home")
    fun homeRobot(): Call<ResponseMessage>

    @POST("robot/calibrate")
    fun calibrateWorkspace(): Call<ResponseMessage>

    @POST("robot/emergency_stop")
    fun emergencyStop(): Call<ResponseMessage>
}

object ApiClient {
    private const val BASE_URL = "http://192.168.100.2:8000/"

    val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val apiService: RobotApiService = retrofit.create(RobotApiService::class.java)
}