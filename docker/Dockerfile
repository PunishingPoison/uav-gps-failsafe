FROM infynex-px4-sitl:jazzy

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install ML, analysis, and ROS/Gazebo bridge extras needed by uav-gps-failsafe
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    "scikit-learn>=1.5.0" \
    "xgboost>=2.0.0" \
    "pandas>=2.2.0" \
    "joblib>=1.3.0"

RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    "matplotlib>=3.9.0"

# Pre-create workspace mount point and build cache dir
WORKDIR /uav_ws
ENTRYPOINT []
CMD ["bash"]
