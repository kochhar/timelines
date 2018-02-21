import Hapi from 'hapi';
import Inert from 'inert';
import config from '../config';
import routes from './api';

const server = Hapi.server({
  host: process.env.HOST || config.DEFAULT_HOST,
  port: process.env.PORT || config.DEFAULT_PORT
});

server.route(routes);

async function start() {
  try {
    
    //below for static file serving
    //TODO: need to replace dist with the output folder of the build process of explorer repo 
    await server.register(Inert);
    server.route({
      method: "GET",
      path: "/{f*}",
      handler: {
        directory: {
          path: './dist',
          listing: true
        }
      }
    });

    //start server
    await server.start();

  } catch (err) {
    console.log(err);
    process.exit(1);
  }
  console.log("Server running at:", server.info.uri);
}

start();