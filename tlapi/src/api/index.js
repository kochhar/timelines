import * as handlers from './handlers'
import Joi from 'joi'

export default [
  {
      method: 'GET',
      path:'/hello', 
      handler: handlers.getStuff,
      config: {
        validate: {
          query: {
            wbId: Joi.string().required()
          }
        }
      }
  }
]