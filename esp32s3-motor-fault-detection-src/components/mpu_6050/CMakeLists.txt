idf_component_register(
    SRCS "mpu_6050.c"
    INCLUDE_DIRS "include"
    PRIV_REQUIRES driver log
)