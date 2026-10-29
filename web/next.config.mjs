const nextConfig = {
  // a self-contained server for the Docker image
  output: "standalone",
  // antd ships ES modules that need transpiling when imported across a server
  // component boundary.
  transpilePackages: ['antd', '@ant-design/icons', 'rc-util', 'rc-pagination', 'rc-picker'],
};

export default nextConfig;
