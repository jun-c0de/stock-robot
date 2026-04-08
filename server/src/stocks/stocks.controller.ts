import { Controller, Get, Query } from '@nestjs/common';
import { StocksService } from './stocks.service';

@Controller('stocks')
export class StocksController {
  constructor(private readonly stocksService: StocksService) {}

  @Get()
  async findAll(
    @Query('page') page?: string,
    @Query('limit') limit?: string,
    @Query('market') market?: string,
  ) {
    return this.stocksService.findAll(
      page ? Math.max(1, parseInt(page, 10)) : 1,
      limit ? Math.min(200, Math.max(1, parseInt(limit, 10))) : 50,
      market,
    );
  }
}
