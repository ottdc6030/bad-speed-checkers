from argparse import ArgumentParser, FileType
from configparser import ConfigParser
from confluent_kafka import Consumer


from event_data import handle_message, set_handlers, save_tables

import signal

def read_args():
    """
    Handler for parsing execution arguments and reading the config file.
    """
    arg_parser = ArgumentParser()

    #File to read for more consistent values across all containers
    arg_parser.add_argument('config_file', type=FileType('r')) 

    # 1 - subscribe only to the events topic
    # 2 - subscribe only to the postgame topic
    # anything else - subscribe to both the events topic and the postgame topic
    arg_parser.add_argument("--watch_topics", type=int, default=0) 

    args = arg_parser.parse_args()

    config=dict()

    config_parser = ConfigParser()
    config_parser.read_file(args.config_file)
    config.update(config_parser["kafka"])
    
    return config, set_handlers(config, args)

def off_trigger(signum, frame):
    """
    Seriously, why doesn't docker pass keyboard interrupts?
    """
    raise KeyboardInterrupt("THIS IS NORMAL")

if __name__ == "__main__":
    config, subscribe_list = read_args()

    print("CONSUMER START")
    consumer = Consumer({
        "bootstrap.servers": config["bootstrap.servers"],
        "group.id": config["group.id"]
    })
    consumer.subscribe(subscribe_list)
    print("CONSUMER SUBSCRIBED")

    signal.signal(signal.SIGTERM, off_trigger)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is not None: 
                handle_message(msg)
    except KeyboardInterrupt:
        pass
    finally:
        print("CLOSING CONSUMER")
        consumer.close()
        save_tables()