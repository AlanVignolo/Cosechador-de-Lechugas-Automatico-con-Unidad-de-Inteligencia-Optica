package com.example.claudio

import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import android.util.Log

class RobotRepository {

    private val apiService = ApiClient.apiService

    fun getRobotStatus(callback: (RobotStatus?, String?) -> Unit) {
        apiService.getRobotStatus().enqueue(object : Callback<RobotStatus> {
            override fun onResponse(call: Call<RobotStatus>, response: Response<RobotStatus>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<RobotStatus>, t: Throwable) {
                Log.e("RobotRepository", "Error getting robot status", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun moveToPosition(x: Double, y: Double, callback: (ResponseMessage?, String?) -> Unit) {
        val request = MoveRequest(x, y)
        apiService.moveToPosition(request).enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error moving to position", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun moveArm(servo1: Int, servo2: Int, timeMs: Int, callback: (ResponseMessage?, String?) -> Unit) {
        val request = ArmMoveRequest(servo1, servo2, timeMs)
        apiService.moveArm(request).enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error moving arm", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun changeArmState(state: String, callback: (ResponseMessage?, String?) -> Unit) {
        apiService.changeArmState(state).enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error changing arm state", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun openGripper(callback: (ResponseMessage?, String?) -> Unit) {
        apiService.openGripper().enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error opening gripper", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun closeGripper(callback: (ResponseMessage?, String?) -> Unit) {
        apiService.closeGripper().enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error closing gripper", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun homeRobot(callback: (ResponseMessage?, String?) -> Unit) {
        apiService.homeRobot().enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error homing robot", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun calibrateWorkspace(callback: (ResponseMessage?, String?) -> Unit) {
        apiService.calibrateWorkspace().enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error calibrating workspace", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }

    fun emergencyStop(callback: (ResponseMessage?, String?) -> Unit) {
        apiService.emergencyStop().enqueue(object : Callback<ResponseMessage> {
            override fun onResponse(call: Call<ResponseMessage>, response: Response<ResponseMessage>) {
                if (response.isSuccessful) {
                    callback(response.body(), null)
                } else {
                    callback(null, "Error: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<ResponseMessage>, t: Throwable) {
                Log.e("RobotRepository", "Error emergency stop", t)
                callback(null, "Error de conexión: ${t.message}")
            }
        })
    }
}