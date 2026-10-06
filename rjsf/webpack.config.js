const path = require('path');

module.exports = {
  entry: './src/index.jsx',
  output: {
    path: path.resolve(__dirname, '../app/static/js'), // Flask's static js folder
    filename: 'rjsf_bundle.js',
  },
  module: {
    rules: [
      {
        test: /\.m?js/,
        resolve: {
          fullySpecified: false,
        },
      },
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env', '@babel/preset-react'],
            sourceType: "unambiguous",
          },
        },
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],   // <- add this
      },
    ],
  },
  resolve: {
    extensions: ['.js', '.jsx'],
  },
  mode: 'production', // or development
};
