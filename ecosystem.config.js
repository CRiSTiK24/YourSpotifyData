module.exports = {
  apps: [
    {
      name: "your-spotify-data",
      cwd: "./backend",
      script: "uv",
      args: "run uvicorn src.main:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
    },
  ],
};
