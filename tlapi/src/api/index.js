import * as handlers from './handlers';
import Joi from 'joi';

export default [
  {
      method: 'POST',
      path:'/api/processDownstream', 
      handler: handlers.processDownstream,
      options: {
        tags: ['downstream'],
        validate: {
          payload: {
            extract: Joi.object().allow(null)
          }
        }
      }
  }
];