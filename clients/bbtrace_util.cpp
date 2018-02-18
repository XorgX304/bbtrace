//#define CSV_IO_NO_THREAD 1
#define MAX_FILE_NAME_LENGTH 512
#define BLOCK_LEN (1<<24)

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <unordered_map>
#include <sstream>
#include <map>
#include "async_reader.h"
#include "bbtrace_core.h"
#include "tracelog_reader.h"
#include "flame_graph.h"

void get_columns(char *line, std::vector<char*>* columns)
{
    char sep = ',';
    char quote = '"';

    for(int i=0; line; i++) {
        char *col_begin = line;
        char *col_end = col_begin;
        while(*col_end != sep && *col_end != '\0') {
            if(*col_end != quote)
                ++col_end;
            else{
                do{
                    ++col_end;
                    while(*col_end != quote){
                        if (*col_end == '\0'){
                            throw std::runtime_error("Escaped string not closed");
                        }
                        ++col_end;
                    }
                    ++col_end;
                }while(*col_end == quote);
            }
        }
        if(*col_end == '\0'){
            line = nullptr;
        }else{
            *col_end = '\0';
            line = col_end + 1;
        }
        columns->push_back(col_begin);
    }
}

int main(int argc, const char* argv[])
{
    if (argc <= 1) {
        std::cout << "Syntax:" << argv[0] << "<trace-log>.0001" << std::endl;
        return 0;
    }

    try
    {
        TraceLog tlog(argv[1]);
        std::ostringstream csvname(tlog.log_name(), std::ios_base::ate);
        csvname << ".csv";
        std::cout << "csvname:" << csvname.str() << std::endl;

        LineReader in(csvname.str());

        std::cout << "reading csv." << std::endl;
        char*line;

        FlameGraph graph;

        do{
            line = in.next_line();
            if(!line) break;

            std::vector<char*> columns;
            get_columns(line, &columns);

            std::vector<char*>::iterator it = columns.begin();
            if (it != columns.end()) {
                if (strcmp(*it, "symbol") == 0) {
                    if (++it == columns.end()) continue;

                    uint entry_pc = atoi(*it);

                    if (graph.BlockExists(entry_pc)) continue;

                    graph.AddBlock({
                        SYMBOL, entry_pc, NONE, 0
                    });
                }
                if (strcmp(*it, "block") == 0) {
                    if (++it == columns.end()) continue;

                    uint entry_pc = atoi(*it);

                    if (graph.BlockExists(entry_pc)) continue;

                    it += 2;
                    if (it == columns.end()) continue;

                    uint end = atoi(*it);

                    it += 2;
                    if (it == columns.end()) continue;

                    char *disasm = *it;
                    char *space = strchr(disasm, ' ');
                    if (space) *space = '\0';

                    block_jump_t jump = NONE;
                    if (*disasm == 'j') {
                        jump = JMP;
                    } else if (strcmp(disasm, "call") == 0) {
                        jump = CALL;
                    } else if (strcmp(disasm, "ret") == 0) {
                        jump = RET;
                    }

                    graph.AddBlock({
                        BLOCK, entry_pc, jump, end
                    });
                }
            }
        } while(true);

        std::cout << "reading tracelog." << std::endl;
        pkt_trace_t *pkt_trace;
        char *dat;
        bool is_run = true;

        for (int d=0; dat = tlog.next_packet(&pkt_trace); d++) {
            app_pc *pc = (app_pc*)dat;
            for(int i=0; i<pkt_trace->size; i++, pc++) {
                uint x = graph.Step(pkt_trace->header.thread, (uint) *pc);
                if (!is_run) break;
            }
            std::cout << ".";
            if (!is_run) break;
        }
        graph.Finish();
        std::cout << std::endl;

        std::ostringstream coachname(tlog.log_name(), std::ios_base::ate);
        coachname << ".cbin";
        const std::string &coachname_str = coachname.str();

        graph.Print(coachname_str.c_str());

    } catch ( std::exception &e )
    {
        std::cerr << "Caught " << e.what( ) << std::endl;
        std::cerr << "Type " << typeid( e ).name( ) << std::endl;
        return -1;
    }
    return 0;
}